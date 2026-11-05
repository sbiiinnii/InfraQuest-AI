from .mission01 import Mission01
from .mission02 import Mission02
from .mission03 import Mission03

# 구현된 미션
MISSIONS = {m.id: m for m in (Mission01(), Mission02(), Mission03())}

# 아직 구현되지 않은 미션(화면에는 '준비 중'으로만 표시). 지금은 없음.
COMING_SOON: list[dict] = []
