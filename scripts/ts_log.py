"""stdin 각 줄 앞에 타임스탬프를 붙여 stdout으로 흘린다 (launchd 로그용)."""
import sys
import time

for line in sys.stdin:
    sys.stdout.write(time.strftime("%Y-%m-%d %H:%M:%S ") + line)
    sys.stdout.flush()
