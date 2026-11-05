"""가상 인프라의 '상태표'.

모든 명령어 출력은 이 상태표를 읽어서 만들어집니다.
(명령어마다 결과를 따로 적어 두지 않기 때문에, 상태와 출력이 서로 모순되지 않습니다.)
"""
from __future__ import annotations

from datetime import datetime, timedelta

HOSTS = {"WEB": "192.168.111.100", "WAS": "192.168.111.200", "DB": "192.168.111.210"}
IP_TO_SERVER = {ip: name for name, ip in HOSTS.items()}
HOSTNAMES = {"WEB": "web01", "WAS": "was01", "DB": "db01"}

SERVICES = {
    "nginx": {"server": "WEB", "port": 80, "proc": "nginx",
              "desc": "A high performance web server and a reverse proxy server"},
    "tomcat10": {"server": "WAS", "port": 8080, "proc": "java",
                 "desc": "Apache Tomcat 10 Web Application Server"},
    "mariadb": {"server": "DB", "port": 3306, "proc": "mariadbd",
                "desc": "MariaDB 10.11.6 database server"},
}

START_TIME = datetime(2026, 11, 5, 14, 2, 0)  # 실습 시작 시각(가상 시계)
BOOT_TIME = datetime(2026, 11, 5, 8, 0, 0)  # 서버가 켜진 시각(커널 로그의 경과 시간 계산용)


def journal_ts(dt: datetime) -> str:
    return dt.strftime("%b %d %H:%M:%S")


def fw_text(rule: dict) -> str:
    return rule["src"] or "Anywhere"


class SimState:
    def __init__(self) -> None:
        self.clock = START_TIME
        self.running = {"nginx": True, "tomcat10": True, "mariadb": True}
        self.pids = {"nginx": 812, "tomcat10": 1043, "mariadb": 655}
        base = datetime(2026, 11, 5, 8, 0, 9)
        self.changed_at = {
            "mariadb": base,
            "nginx": base + timedelta(seconds=3),
            "tomcat10": base + timedelta(seconds=6),
        }
        self.next_pid = 1500
        self.next_conn_id = 14
        # 방화벽: 활성화되면 위에서부터 처음 맞는 규칙이 적용되고, 어디에도 안 맞으면 차단(DENY)
        self.ufw = {s: {"active": False, "rules": []} for s in HOSTS}
        self.journal: dict[str, list[str]] = {s: [] for s in SERVICES}
        self.nginx_error_log: list[str] = []
        self.ufw_logs: dict[str, list[str]] = {s: [] for s in HOSTS}  # /var/log/ufw.log
        self.tomcat_log: list[str] = []  # /var/log/tomcat10/catalina.out (WAS)
        self._blocked = 0
        for svc in SERVICES:
            at = self.changed_at[svc]
            self.jlog(svc, f"Started {svc}.service - {SERVICES[svc]['desc']}.", at)

    # ---------- 시간 / 로그 ----------
    def tick(self, seconds: int = 7) -> None:
        self.clock += timedelta(seconds=seconds)

    def jlog(self, svc: str, text: str, when: datetime | None = None) -> None:
        when = when or self.clock
        host = HOSTNAMES[SERVICES[svc]["server"]]
        self.journal[svc].append(f"{journal_ts(when)} {host} systemd[1]: {text}")

    # ---------- 서비스 제어 ----------
    def start_service(self, svc: str) -> bool:
        if self.running[svc]:
            return False
        self.jlog(svc, f"Starting {svc}.service - {SERVICES[svc]['desc']}...")
        self.running[svc] = True
        self.pids[svc] = self.next_pid
        self.next_pid += 37
        self.changed_at[svc] = self.clock
        self.jlog(svc, f"Started {svc}.service - {SERVICES[svc]['desc']}.")
        return True

    def stop_service(self, svc: str) -> bool:
        if not self.running[svc]:
            return False
        self.jlog(svc, f"Stopping {svc}.service - {SERVICES[svc]['desc']}...")
        self.jlog(svc, f"{svc}.service: Deactivated successfully.")
        self.jlog(svc, f"Stopped {svc}.service - {SERVICES[svc]['desc']}.")
        self.running[svc] = False
        self.changed_at[svc] = self.clock
        return True

    def restart_service(self, svc: str) -> bool:
        self.stop_service(svc)
        self.start_service(svc)
        return True

    # ---------- 네트워크 ----------
    def listening(self, server: str) -> list[tuple[int, str, int]]:
        """(포트, 프로세스 이름, PID) 목록"""
        rows = [(22, "sshd", 701)]
        for svc, info in SERVICES.items():
            if info["server"] == server and self.running[svc]:
                rows.append((info["port"], info["proc"], self.pids[svc]))
        return sorted(rows)

    def is_listening(self, server: str, port: int) -> bool:
        return any(p == port for p, _, _ in self.listening(server))

    def _fw_decision(self, dst: str, src_ip: str, port: int) -> str:
        fw = self.ufw[dst]
        if not fw["active"]:
            return "ALLOW"
        for rule in fw["rules"]:
            if rule["port"] == port and rule["src"] in (None, src_ip):
                return rule["action"]
        return "DENY"  # ufw 기본 정책: 들어오는 연결 차단

    def log_ufw_block(self, dst: str, src: str, port: int, when: datetime | None = None) -> None:
        """방화벽이 연결을 막으면 /var/log/ufw.log 에 기록이 남습니다."""
        when = when or self.clock
        self._blocked += 1
        n = self._blocked
        up = (when - BOOT_TIME).total_seconds()
        self.ufw_logs[dst].append(
            f"{when:%b} {when.day:>2} {when:%H:%M:%S} {HOSTNAMES[dst]} kernel: [{up:>12.6f}] [UFW BLOCK] "
            f"IN=ens33 OUT= MAC=00:0c:29:aa:bb:cc:00:0c:29:dd:ee:ff:08:00 SRC={HOSTS[src]} DST={HOSTS[dst]} "
            f"LEN=60 TOS=0x00 PREC=0x00 TTL=64 ID={21000 + n * 53} DF PROTO=TCP SPT={40000 + n * 37} DPT={port} "
            f"WINDOW=64240 RES=0x00 SYN URGP=0")

    def tcp_connect(self, src: str, dst_ip: str, port: int, log: bool = True) -> str:
        """'ok' | 'refused'(연결 거부) | 'timeout'(응답 없음) | 'unreachable'
        log=False 는 '상태만 살펴볼 때' 사용합니다(로그가 쌓이지 않음)."""
        dst = IP_TO_SERVER.get(dst_ip)
        if dst is None:
            return "unreachable"
        if src != dst:  # 자기 자신(루프백)에는 방화벽이 적용되지 않음
            decision = self._fw_decision(dst, HOSTS[src], port)
            if decision != "ALLOW":
                if log:
                    self.log_ufw_block(dst, src, port)
                return "refused" if decision == "REJECT" else "timeout"
        return "ok" if self.is_listening(dst, port) else "refused"

    def app_status(self) -> int:
        """WAS의 웹 애플리케이션이 요청에 답하는 상태 코드. DB(3306)에 연결할 수 있으면 200, 없으면 500."""
        return 200 if self.tcp_connect("WAS", HOSTS["DB"], 3306, log=False) == "ok" else 500

    def log_app_db_error(self, when: datetime | None = None) -> None:
        """앱이 DB에 연결하지 못해 500을 돌려줄 때, Tomcat 로그(catalina.out)에 오류가 남습니다."""
        when = when or self.clock
        reason = ("Connection refused" if self.tcp_connect("WAS", HOSTS["DB"], 3306, log=False) == "refused"
                  else "Connect timed out")
        n = len(self.tomcat_log) % 8 + 1
        self.tomcat_log.append(
            f"{when:%d-%b-%Y %H:%M:%S}.{(when.second * 37) % 1000:03d} SEVERE [http-nio-8080-exec-{n}] "
            f"org.apache.catalina.core.StandardWrapperValve.invoke Servlet.service() for servlet [shop] threw exception: "
            f"java.sql.SQLNonTransientConnectionException: Could not connect to address=(host={HOSTS['DB']})(port=3306)"
            f"(type=master) : {reason}")

    def web_path_ok(self) -> bool:
        """사용자가 WEB 주소로 접속했을 때 정상 응답(200)이 나오는 상태인가? (로그를 남기지 않고 계산)"""
        return (self.running["nginx"] and self.running["tomcat10"]
                and self.tcp_connect("WEB", HOSTS["WAS"], 8080, log=False) == "ok"
                and self.app_status() == 200)

    def _app_response(self, via: str) -> dict:
        status = self.app_status()
        if status == 500:
            self.log_app_db_error()
        return {"outcome": "http", "status": status, "via": via}

    def http_request(self, src: str, dst_ip: str, port: int, host: str, client: str) -> dict:
        """HTTP 요청 한 번을 시뮬레이션해서 결과를 돌려줍니다."""
        conn = self.tcp_connect(src, dst_ip, port)
        if conn != "ok":
            return {"outcome": conn}
        dst = IP_TO_SERVER[dst_ip]
        if dst == "WEB" and port == 80:  # Nginx: 요청을 WAS(8080)로 넘김(리버스 프록시)
            up = self.tcp_connect("WEB", HOSTS["WAS"], 8080)
            if up == "ok":  # WAS가 답을 주면 Nginx는 그대로 전달합니다(앱이 500이면 500 그대로)
                return self._app_response("nginx")
            self.next_conn_id += 1
            worker = self.pids["nginx"] + 1
            if up == "refused":
                reason, status = "connect() failed (111: Connection refused) while connecting to upstream", 502
            else:
                reason, status = "upstream timed out (110: Connection timed out) while connecting to upstream", 504
            self.nginx_error_log.append(
                f'{self.clock:%Y/%m/%d %H:%M:%S} [error] {worker}#{worker}: *{self.next_conn_id} {reason}, '
                f'client: {client}, server: _, request: "GET / HTTP/1.1", '
                f'upstream: "http://{HOSTS["WAS"]}:8080/", host: "{host}"'
            )
            return {"outcome": "http", "status": status, "via": "nginx"}
        if dst == "WAS" and port == 8080:
            return self._app_response("tomcat")
        return {"outcome": "non_http"}  # 22, 3306 등은 HTTP 서버가 아님


def healthy_state() -> SimState:
    return SimState()
