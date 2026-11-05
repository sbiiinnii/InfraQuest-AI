"""명령어 해석기: 입력한 한 줄을 읽고, 상태표(SimState)를 근거로 출력을 만듭니다.

LLM은 여기에 관여하지 않습니다. 같은 상태에서는 항상 같은 출력이 나옵니다.
"""
from __future__ import annotations

import ipaddress
import shlex
from dataclasses import dataclass, field
from datetime import timedelta
from urllib.parse import urlsplit

from .state import HOSTNAMES, HOSTS, IP_TO_SERVER, SERVICES, SimState, fw_text

NGINX_VER = "nginx/1.24.0 (Ubuntu)"
OUT_OF_SCOPE_UNITS = {"ssh", "sshd", "ufw", "cron", "systemd-resolved", "rsyslog"}
PORT_NAMES = {22: "ssh", 80: "http", 8080: "http-alt", 3306: "mysql"}

NGINX_CONF = """server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    location / {
        proxy_pass http://192.168.111.200:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}"""

TOMCAT_BODY = (
    "<!DOCTYPE html>\n<html><head><title>InfraQuest Shop</title></head>\n"
    "<body><h1>InfraQuest Shop</h1><p>Welcome! The service is running normally.</p></body></html>"
)

TOMCAT_500_BODY = (
    '<!doctype html><html lang="en"><head><title>HTTP Status 500 – Internal Server Error</title></head>\n'
    "<body><h1>HTTP Status 500 – Internal Server Error</h1><hr/><h3>Apache Tomcat/10.1.16</h3></body></html>"
)

HELP_TEXT = """사용할 수 있는 명령어 (가상 터미널)
  systemctl status|start|stop|restart|is-active <서비스>
  service <서비스> status|start|stop|restart
  ss -tulnp
  curl [-s -S -L -k -i -I] <URL>
  journalctl -u <서비스> [-n 줄수]
  cat <파일>      (/etc/nginx/sites-enabled/default, /var/log/nginx/error.log, /var/log/ufw.log,
                   /var/log/tomcat10/catalina.out)
  tail [-n 줄수] <파일>
  ufw status [verbose|numbered]
  ufw allow|deny|reject <규칙>   ufw insert <번호> <동작> <규칙>
  ufw delete <번호 | 동작 규칙>   ufw enable|disable|reload
    (규칙 예: 8080/tcp  또는  from 192.168.111.100 to any port 8080 proto tcp)
  hostname [-I], ip a
  clear, help
※ 파이프(|), 리다이렉션(>), 명령어 연결(; &&)은 지원하지 않아요. 한 줄에 명령어 하나씩 입력해 주세요.
※ 확인 질문(y/n)에는 가상 터미널이 자동으로 y로 답해요.
※ 이곳은 가상 환경이에요. 실제 서버에는 아무 영향이 없습니다."""


@dataclass
class Result:
    output: str
    exit_code: int = 0
    supported: bool = True
    counted: bool = True  # '실행한 명령어 수'에 포함할지
    facts: dict = field(default_factory=dict)  # 판정용 사실 기록(화면에는 노출하지 않음)


def _sim(msg: str) -> Result:
    return Result(f"[가상 터미널] {msg}", 127, supported=False, facts={"kind": "unsupported"})


def _ago(delta: timedelta) -> str:
    s = int(delta.total_seconds())
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}min"
    return f"{s // 3600}h"


def _systemd_ts(dt) -> str:
    return f"{dt:%a %Y-%m-%d %H:%M:%S} KST"


# ---------------------------------------------------------------- 진입점
def execute(st: SimState, server: str, line: str) -> Result:
    if any(ch in line for ch in "|;&><`") or "$(" in line:
        return _sim("파이프(|), 리다이렉션(>), 명령어 연결(; &&)은 지원하지 않아요. 명령어를 하나씩 입력해 주세요.")
    try:
        argv = shlex.split(line)
    except ValueError:
        return Result("bash: unexpected EOF while looking for matching quote", 2, supported=False,
                      facts={"kind": "unsupported"})
    if not argv:
        return Result("", counted=False, facts={"kind": "noop"})
    if argv[0] == "sudo":  # 이 터미널은 root 권한으로 동작합니다
        argv = argv[1:]
        if not argv:
            return _sim("sudo 뒤에 실행할 명령어를 입력해 주세요.")
    cmd, args = argv[0], argv[1:]
    handler = HANDLERS.get(cmd)
    if handler is None:
        return _sim(f"'{cmd}'은(는) 지원하지 않는 명령어예요. 'help'를 입력하면 사용할 수 있는 명령어를 볼 수 있어요.")
    return handler(st, server, args)


# ---------------------------------------------------------------- systemctl / service
def _render_status(st: SimState, svc: str) -> str:
    info = SERVICES[svc]
    running = st.running[svc]
    since = st.changed_at[svc]
    ago = _ago(st.clock - since)
    lines = [
        f"{'●' if running else '○'} {svc}.service - {info['desc']}",
        f"     Loaded: loaded (/lib/systemd/system/{svc}.service; enabled; preset: enabled)",
    ]
    if running:
        lines += [
            f"     Active: active (running) since {_systemd_ts(since)}; {ago} ago",
            f"   Main PID: {st.pids[svc]} ({info['proc']})",
        ]
    else:
        lines.append(f"     Active: inactive (dead) since {_systemd_ts(since)}; {ago} ago")
    lines.append("")
    lines += st.journal[svc][-3:]
    return "\n".join(lines)


def _unit_here(server: str, svc: str) -> bool:
    return svc in SERVICES and SERVICES[svc]["server"] == server


def cmd_systemctl(st: SimState, server: str, args: list[str]) -> Result:
    pos = [a for a in args if not a.startswith("-")]
    if len(pos) < 2:
        return _sim("서비스 이름까지 입력해 주세요. 예: systemctl status nginx")
    sub, unit = pos[0], pos[1]
    if sub not in {"status", "start", "stop", "restart", "is-active"}:
        return _sim(f"'systemctl {sub}'는 이번 실습에서 지원하지 않아요. (status, start, stop, restart, is-active)")
    svc = unit[: -len(".service")] if unit.endswith(".service") else unit
    return _service_action(st, server, sub, svc)


def cmd_service(st: SimState, server: str, args: list[str]) -> Result:
    if len(args) != 2 or args[1] not in {"status", "start", "stop", "restart"}:
        return _sim("사용법: service <서비스> status|start|stop|restart")
    return _service_action(st, server, args[1], args[0])


def _service_action(st: SimState, server: str, sub: str, svc: str) -> Result:
    if not _unit_here(server, svc):
        if svc in OUT_OF_SCOPE_UNITS:
            return _sim(f"'{svc}' 서비스는 이번 실습에서 다루지 않아요.")
        facts = {"kind": "svc_missing", "service": svc, "server": server}
        if sub == "status":
            return Result(f"Unit {svc}.service could not be found.", 4, facts=facts)
        if sub == "is-active":
            return Result("inactive", 3, facts=facts)
        return Result(f"Failed to {sub} {svc}.service: Unit {svc}.service not found.", 5, facts=facts)

    if sub == "status":
        running = st.running[svc]
        return Result(_render_status(st, svc), 0 if running else 3,
                      facts={"kind": "svc_status", "service": svc, "server": server, "running": running})
    if sub == "is-active":
        running = st.running[svc]
        return Result("active" if running else "inactive", 0 if running else 3,
                      facts={"kind": "svc_status", "service": svc, "server": server, "running": running})

    if sub == "start":
        changed = st.start_service(svc)
    elif sub == "stop":
        changed = st.stop_service(svc)
    else:
        changed = st.restart_service(svc)
    return Result("", 0, facts={"kind": "svc_action", "service": svc, "server": server, "action": sub,
                                "changed": changed, "mutated": changed, "running": st.running[svc]})


# ---------------------------------------------------------------- ss
def cmd_ss(st: SimState, server: str, args: list[str]) -> Result:
    flags = "".join(a.lstrip("-") for a in args if a.startswith("-"))
    if args and any(not a.startswith("-") for a in args):
        return _sim("ss는 옵션만 지원해요. 예: ss -tulnp")
    if not flags or any(c not in "tulnp" for c in flags) or "l" not in flags:
        return _sim("ss는 '-tulnp'처럼 l(리스닝) 옵션이 포함된 형태만 지원해요. 예: ss -tulnp")
    show_proc, numeric = "p" in flags, "n" in flags
    head = f"{'Netid':<6}{'State':<7}{'Recv-Q':<7}{'Send-Q':<7}{'Local Address:Port':>22}  {'Peer Address:Port':<18}"
    if show_proc:
        head += "Process"
    out = [head.rstrip()]
    ports = []
    if "t" in flags or "u" not in flags:
        for port, proc, pid in st.listening(server):
            ports.append(port)
            local_ip = "*" if proc == "java" else "0.0.0.0"
            peer = "*" if proc == "java" else "0.0.0.0:*"
            if proc == "java":
                peer = "*:*"
            name = str(port) if numeric else PORT_NAMES.get(port, str(port))
            row = f"{'tcp':<6}{'LISTEN':<7}{0:<7}{128:<7}{local_ip + ':' + name:>22}  {peer:<18}"
            if show_proc:
                if proc == "nginx":
                    row += f'users:(("nginx",pid={pid + 1},fd=5),("nginx",pid={pid},fd=5))'
                else:
                    row += f'users:(("{proc}",pid={pid},fd=3))'
            out.append(row.rstrip())
    return Result("\n".join(out), facts={"kind": "ports", "server": server, "ports": ports})


# ---------------------------------------------------------------- curl
_SHORT = set("sSLkiI4")
_LONG = {"--silent": "s", "--show-error": "S", "--location": "L", "--insecure": "k",
         "--include": "i", "--head": "I"}


def _http_text(status: int, via: str, body: str, st: SimState, head: bool, include: bool) -> str:
    if status == 500:  # 앱(Tomcat)이 만든 오류 페이지. Nginx를 거쳐도 내용은 그대로 전달됩니다.
        shown = TOMCAT_500_BODY
        common = ["Content-Type: text/html;charset=utf-8", f"Content-Length: {len(shown.encode())}"]
        if via == "nginx":
            headers = ["HTTP/1.1 500 Internal Server Error", f"Server: {NGINX_VER}", f"Date: {_gmt(st)}", *common,
                       "Connection: close"]
        else:
            headers = ["HTTP/1.1 500 ", *common, f"Date: {_gmt(st)}", "Connection: close"]
    elif via == "nginx":
        reason = {200: "OK", 502: "Bad Gateway", 504: "Gateway Time-out"}[status]
        if status == 200:
            ctype, shown = "text/html;charset=UTF-8", TOMCAT_BODY
        else:
            ctype = "text/html"
            shown = (f"<html>\r\n<head><title>{status} {reason}</title></head>\r\n<body>\r\n"
                     f"<center><h1>{status} {reason}</h1></center>\r\n<hr><center>{NGINX_VER}</center>\r\n</body>\r\n</html>")
        first = f"HTTP/1.1 {status} {reason if status != 200 else 'OK'}"
        headers = [first, f"Server: {NGINX_VER}", f"Date: {_gmt(st)}", f"Content-Type: {ctype}",
                   f"Content-Length: {len(shown.encode())}", "Connection: keep-alive"]
    else:
        shown = TOMCAT_BODY
        headers = ["HTTP/1.1 200 ", "Content-Type: text/html;charset=UTF-8",
                   f"Content-Length: {len(shown.encode())}", f"Date: {_gmt(st)}"]
    if head:
        return "\n".join(headers) + "\n"
    if include:
        return "\n".join(headers) + "\n\n" + shown
    return shown


def _gmt(st: SimState) -> str:
    return (st.clock - timedelta(hours=9)).strftime("%a, %d %b %Y %H:%M:%S GMT")


def cmd_curl(st: SimState, server: str, args: list[str]) -> Result:
    opts: set[str] = set()
    urls: list[str] = []
    for a in args:
        if a in _LONG:
            opts.add(_LONG[a])
        elif a.startswith("--"):
            return _sim(f"curl 옵션 {a}은(는) 지원하지 않아요. (지원: -s -S -L -k -i -I)")
        elif a.startswith("-") and len(a) > 1:
            for ch in a[1:]:
                if ch not in _SHORT:
                    return _sim(f"curl 옵션 -{ch}은(는) 지원하지 않아요. (지원: -s -S -L -k -i -I)")
                opts.add(ch)
        else:
            urls.append(a)
    if not urls:
        return Result("curl: try 'curl --help' or 'curl --manual' for more information", 2, supported=False,
                      facts={"kind": "unsupported"})
    raw = urls[0]
    if "://" not in raw:
        raw = "http://" + raw
    parts = urlsplit(raw)
    scheme, host = parts.scheme, parts.hostname
    if not host:
        return Result("curl: (3) URL rejected: No host part in the URL", 3, facts={"kind": "curl_error"})
    try:
        port = parts.port or (443 if scheme == "https" else 80)
    except ValueError:
        return Result("curl: (3) URL rejected: Port number was not a decimal number between 0 and 65535", 3,
                      facts={"kind": "curl_error"})

    # 주소 해석
    if host == "localhost" or host == "127.0.0.1":
        dst_ip, client = HOSTS[server], "127.0.0.1"
    else:
        try:
            ipaddress.IPv4Address(host)
        except ValueError:
            return _curl_fail(opts, f"curl: (6) Could not resolve host: {host}", 6, server, None, port, "unresolved")
        dst_ip, client = host, HOSTS[server]

    res = st.http_request(server, dst_ip, port, host, client)
    outcome = res["outcome"]
    dst_server = IP_TO_SERVER.get(dst_ip)
    facts = {"kind": "curl", "src": server, "dst_server": dst_server, "port": port,
             "outcome": outcome, "status": res.get("status")}
    if outcome == "refused":
        return _curl_fail(opts, f"curl: (7) Failed to connect to {host} port {port} after 1 ms: Couldn't connect to server",
                          7, server, dst_server, port, outcome)
    if outcome == "timeout":
        return _curl_fail(opts, f"curl: (28) Failed to connect to {host} port {port} after 130283 ms: Couldn't connect to server",
                          28, server, dst_server, port, outcome)
    if outcome == "unreachable":
        return _curl_fail(opts, f"curl: (7) Failed to connect to {host} port {port} after 3054 ms: No route to host",
                          7, server, dst_server, port, outcome)
    if outcome == "non_http":
        return _curl_fail(opts, "curl: (1) Received HTTP/0.9 when not allowed", 1, server, dst_server, port, outcome)
    if scheme == "https":
        return _curl_fail(opts, "curl: (35) error:0A00010B:SSL routines::wrong version number", 35, server, dst_server,
                          port, "tls_error")
    text = _http_text(res["status"], res["via"], "", st, head="I" in opts, include="i" in opts)
    return Result(text, 0, facts=facts)


def _curl_fail(opts: set[str], msg: str, code: int, src: str, dst_server, port: int, outcome: str) -> Result:
    shown = "" if ("s" in opts and "S" not in opts) else msg  # -s는 오류 메시지도 숨김(-S와 함께 쓰면 표시)
    return Result(shown, code, facts={"kind": "curl", "src": src, "dst_server": dst_server, "port": port,
                                      "outcome": outcome, "status": None})


# ---------------------------------------------------------------- journalctl / cat / tail
def cmd_journalctl(st: SimState, server: str, args: list[str]) -> Result:
    unit, lines, i = None, None, 0
    while i < len(args):
        a = args[i]
        if a in ("-u", "--unit") and i + 1 < len(args):
            unit, i = args[i + 1], i + 2
            continue
        if a.startswith("--unit="):
            unit = a.split("=", 1)[1]
        elif a in ("-n", "--lines") and i + 1 < len(args) and args[i + 1].isdigit():
            lines, i = int(args[i + 1]), i + 2
            continue
        elif a.startswith("--lines=") and a.split("=", 1)[1].isdigit():
            lines = int(a.split("=", 1)[1])
        elif a.startswith("-n") and a[2:].isdigit():
            lines = int(a[2:])
        elif a in ("--no-pager", "-x", "-e", "-xe", "-ex"):
            pass
        else:
            return _sim(f"journalctl 옵션 '{a}'은(는) 지원하지 않아요. 예: journalctl -u tomcat10 -n 20")
        i += 1
    if unit is None:
        return _sim("서비스를 지정해 주세요. 예: journalctl -u tomcat10")
    svc = unit[: -len(".service")] if unit.endswith(".service") else unit
    here = _unit_here(server, svc)
    entries = st.journal[svc] if here else []
    shown = entries[-lines:] if lines else entries
    out = "\n".join(shown) if shown else "-- No entries --"
    return Result(out, facts={"kind": "journal", "service": svc, "server": server, "here": here,
                              "running": st.running.get(svc) if here else None})


FILES = {  # 경로: (있는 서버 또는 None=모든 서버, 내용을 만드는 함수, 판정용 이름)
    "/etc/nginx/sites-enabled/default": ("WEB", lambda st, sv: NGINX_CONF, "nginx_config"),
    "/var/log/nginx/error.log": ("WEB", lambda st, sv: "\n".join(st.nginx_error_log), "nginx_error_log"),
    "/var/log/ufw.log": (None, lambda st, sv: "\n".join(st.ufw_logs[sv]), "ufw_log"),
    "/var/log/tomcat10/catalina.out": ("WAS", lambda st, sv: "\n".join(st.tomcat_log), "tomcat_log"),
}


def _read_file(st: SimState, server: str, path: str, tail: int | None, cmd: str) -> Result:
    if path not in FILES:
        return _sim(f"'{path}' 파일은 이번 실습에서 열 수 없어요. (열 수 있는 파일: {', '.join(FILES)})")
    owner, getter, key = FILES[path]
    missing = owner is not None and owner != server
    # 방화벽을 켠 적도 없고 기록도 없는 서버에는 ufw.log 파일이 없습니다.
    if key == "ufw_log" and not st.ufw[server]["active"] and not st.ufw_logs[server]:
        missing = True
    if missing:
        return Result(f"{cmd}: {path}: No such file or directory", 1, facts={"kind": "file_missing", "path": path})
    content = getter(st, server)
    if tail is not None:
        content = "\n".join(content.splitlines()[-tail:])
    return Result(content, facts={"kind": "read_file", "file": key, "server": server, "empty": not content.strip()})


def cmd_cat(st: SimState, server: str, args: list[str]) -> Result:
    if len(args) != 1 or args[0].startswith("-"):
        return _sim("사용법: cat <파일 경로>")
    return _read_file(st, server, args[0], None, "cat")


def cmd_tail(st: SimState, server: str, args: list[str]) -> Result:
    n, path, i = 10, None, 0
    while i < len(args):
        a = args[i]
        if a == "-n" and i + 1 < len(args) and args[i + 1].isdigit():
            n, i = int(args[i + 1]), i + 2
            continue
        if a.startswith("-n") and a[2:].isdigit():
            n = int(a[2:])
        elif a.startswith("-") and a[1:].isdigit():
            n = int(a[1:])
        elif a.startswith("-"):
            return _sim("tail은 -n 줄수 옵션만 지원해요. (-f는 지원하지 않아요)")
        elif path is None:
            path = a
        else:
            return _sim("tail은 파일 하나만 지원해요.")
        i += 1
    if path is None:
        return _sim("사용법: tail [-n 줄수] <파일 경로>")
    return _read_file(st, server, path, n, "tail")


# ---------------------------------------------------------------- ufw / hostname / ip
def _rule_to(r: dict) -> str:
    return f"{r['port']}/{r['proto']}" if r.get("proto") else str(r["port"])


def _rule_text(r: dict) -> str:
    """'reject from 192.168.111.100 to any port 8080 proto tcp' 형태의 설명"""
    act = r["action"].lower()
    if r["src"]:
        return f"{act} from {r['src']} to any port {r['port']}" + (f" proto {r['proto']}" if r.get("proto") else "")
    return f"{act} {_rule_to(r)}"


def _parse_rule(tokens: list[str]) -> tuple[int, str | None, str | None]:
    """(포트, 프로토콜, 출발지IP)로 해석합니다. 지원 형태: '8080/tcp' / 'from IP to any port 8080 [proto tcp]'"""
    def port_of(tok: str, allow_proto: bool) -> tuple[int, str | None]:
        num, _, proto = tok.partition("/")
        if not num.isdigit() or not 1 <= int(num) <= 65535:
            raise ValueError(f"포트 '{num}'이(가) 올바르지 않아요. (1~65535)")
        if proto and not allow_proto:
            raise ValueError("'from ... port' 형태에서는 포트 뒤에 /tcp를 붙이지 않고 'proto tcp'를 써요.")
        if proto not in ("", "tcp"):
            raise ValueError("이번 실습에서는 tcp만 지원해요.")
        return int(num), (proto or None)

    if len(tokens) == 1:
        port, proto = port_of(tokens[0], True)
        return port, proto, None
    if len(tokens) in (6, 8) and tokens[0] == "from" and tokens[2:5] == ["to", "any", "port"]:
        src = None if tokens[1] == "any" else tokens[1]
        if src is not None:
            try:
                ipaddress.IPv4Address(src)
            except ValueError:
                raise ValueError(f"IP 주소 '{src}'이(가) 올바르지 않아요.")
        port, _ = port_of(tokens[5], False)
        proto = None
        if len(tokens) == 8:
            if tokens[6:] != ["proto", "tcp"]:
                raise ValueError("이번 실습에서는 'proto tcp'만 지원해요.")
            proto = "tcp"
        return port, proto, src
    raise ValueError("규칙 형태는 '8080/tcp' 또는 'from 192.168.111.100 to any port 8080 proto tcp'만 지원해요.")


UFW_USAGE = ("ufw는 status [verbose|numbered], allow|deny|reject <규칙>, insert <번호> <동작> <규칙>, "
             "delete <번호|동작 규칙>, enable, disable, reload 를 지원해요.")
ACTIONS = {"allow": "ALLOW", "deny": "DENY", "reject": "REJECT"}


def _ufw_status(fw: dict, mode: str | None) -> str:
    if not fw["active"]:
        return "Status: inactive"
    lines = ["Status: active"]
    if mode == "verbose":
        lines += ["Logging: on (low)", "Default: deny (incoming), allow (outgoing), disabled (routed)",
                  "New profiles: skip"]
    lines.append("")
    if mode == "numbered":
        lines += [f"{'':<5}{'To':<27}{'Action':<12}From", f"{'':<5}{'--':<27}{'------':<12}----"]
        for i, r in enumerate(fw["rules"], 1):
            lines.append(f"{'[' + str(i).rjust(2) + '] ':<5}{_rule_to(r):<27}{r['action'] + ' IN':<12}{fw_text(r)}")
    else:
        lines += [f"{'To':<27}{'Action':<12}From", f"{'--':<27}{'------':<12}----"]
        for r in fw["rules"]:
            lines.append(f"{_rule_to(r):<27}{r['action']:<12}{fw_text(r)}")
    return "\n".join(lines)


def cmd_ufw(st: SimState, server: str, args: list[str]) -> Result:
    args = [a for a in args if a != "--force"]  # 가상 터미널은 확인 질문에 자동으로 y로 답합니다
    if not args:
        return _sim(UFW_USAGE)
    sub, rest = args[0], args[1:]
    fw = st.ufw[server]

    if sub == "status":
        if len(rest) > 1 or (rest and rest[0] not in ("verbose", "numbered")):
            return _sim("ufw status 는 'verbose' 또는 'numbered'만 함께 쓸 수 있어요.")
        return Result(_ufw_status(fw, rest[0] if rest else None),
                      facts={"kind": "ufw_status", "server": server, "active": fw["active"],
                             "rules": [dict(r) for r in fw["rules"]]})

    before = st.tcp_connect("WEB", HOSTS["WAS"], 8080, log=False)
    changed, out, broad = False, "", False

    if sub in ("enable", "disable", "reload"):
        if rest:
            return _sim(UFW_USAGE)
        if sub == "enable":
            changed, fw["active"] = not fw["active"], True
            out = "Firewall is active and enabled on system startup"
        elif sub == "disable":
            changed, fw["active"] = fw["active"], False
            out = "Firewall stopped and disabled on system startup"
        else:
            out = "Firewall reloaded" if fw["active"] else "Firewall not enabled (skipping reload)"
    elif sub in ACTIONS or sub == "insert":
        pos = None
        if sub == "insert":
            if len(rest) < 3 or not rest[0].isdigit() or rest[1] not in ACTIONS:
                return _sim("사용법: ufw insert <번호> allow|deny|reject <규칙>")
            pos, action, spec = int(rest[0]), ACTIONS[rest[1]], rest[2:]
            if not 1 <= pos <= len(fw["rules"]) + 1:
                return Result(f"ERROR: Invalid position '{pos}'", 1, facts={"kind": "ufw_error"})
        else:
            action, spec = ACTIONS[sub], rest
        try:
            port, proto, src = _parse_rule(spec)
        except ValueError as e:
            return _sim(str(e))
        rule = {"port": port, "proto": proto, "action": action, "src": src}
        if rule in fw["rules"]:
            out = "Skipping inserting existing rule" if pos else "Skipping adding existing rule"
        else:
            fw["rules"].insert(pos - 1 if pos else len(fw["rules"]), rule)  # 일반 추가는 맨 끝에 붙음
            changed = True
            broad = action == "ALLOW" and src is None
            out = "Rule inserted" if pos else "Rule added"
    elif sub == "delete":
        if not rest:
            return _sim("사용법: ufw delete <번호> 또는 ufw delete <동작> <규칙>")
        if len(rest) == 1 and rest[0].isdigit():
            n = int(rest[0])
            if not 1 <= n <= len(fw["rules"]):
                return Result(f"ERROR: Could not find rule '{n}'", 1, facts={"kind": "ufw_error"})
            gone = fw["rules"].pop(n - 1)
            changed = True
            out = f"Deleting:\n {_rule_text(gone)}\nProceed with operation (y|n)? y\nRule deleted"
        elif rest[0] in ACTIONS:
            try:
                port, proto, src = _parse_rule(rest[1:])
            except ValueError as e:
                return _sim(str(e))
            hit = next((r for r in fw["rules"] if r["action"] == ACTIONS[rest[0]] and r["port"] == port
                        and r["src"] == src and (proto is None or r["proto"] == proto)), None)
            if hit is None:
                out = "Could not delete non-existent rule"
            else:
                fw["rules"].remove(hit)
                changed, out = True, "Rule deleted"
        else:
            return _sim("사용법: ufw delete <번호> 또는 ufw delete <동작> <규칙>")
    else:
        return _sim(UFW_USAGE)

    after = st.tcp_connect("WEB", HOSTS["WAS"], 8080, log=False)
    facts = {"kind": "ufw_change", "server": server, "action": sub, "changed": changed, "mutated": changed,
             "unblocked_web_to_was": before != "ok" and after == "ok", "broad_allow": broad}
    return Result(out, 1 if "non-existent" in out else 0, facts=facts)


def cmd_hostname(st: SimState, server: str, args: list[str]) -> Result:
    if not args:
        return Result(HOSTNAMES[server], facts={"kind": "info"})
    if args == ["-I"]:
        return Result(HOSTS[server], facts={"kind": "info"})
    return _sim("hostname은 'hostname'과 'hostname -I'만 지원해요.")


def cmd_ip(st: SimState, server: str, args: list[str]) -> Result:
    if args not in (["a"], ["addr"], ["address"]):
        return _sim("ip는 'ip a'만 지원해요.")
    out = (
        "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000\n"
        "    inet 127.0.0.1/8 scope host lo\n"
        "2: ens33: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000\n"
        f"    inet {HOSTS[server]}/24 brd 192.168.111.255 scope global ens33"
    )
    return Result(out, facts={"kind": "info"})


def cmd_help(st: SimState, server: str, args: list[str]) -> Result:
    return Result(HELP_TEXT, counted=False, facts={"kind": "help"})


def cmd_clear(st: SimState, server: str, args: list[str]) -> Result:
    return Result("", counted=False, facts={"kind": "clear"})


HANDLERS = {
    "systemctl": cmd_systemctl, "service": cmd_service, "ss": cmd_ss, "curl": cmd_curl,
    "journalctl": cmd_journalctl, "cat": cmd_cat, "tail": cmd_tail, "ufw": cmd_ufw,
    "hostname": cmd_hostname, "ip": cmd_ip, "help": cmd_help, "clear": cmd_clear,
}
