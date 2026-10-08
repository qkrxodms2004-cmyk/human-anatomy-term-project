"""Windows에서는 프로젝트에 포함된 NumPy와 Pygame을 먼저 사용합니다."""
from pathlib import Path
import sys
import sysconfig


def configure_vendor() -> Path | None:
    # 다른 운영체제의 기존 개발 환경에는 영향을 주지 않습니다.
    if sys.platform != "win32":
        return None
    if (sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 11)
            or sys.maxsize <= 2**32 or sysconfig.get_platform().replace("-", "_") != "win_amd64"):
        raise RuntimeError(
            "동봉된 라이브러리는 Windows x64용 CPython 3.11(64비트) 전용입니다. "
            "Python 3.11 64비트로 실행하세요. pip 설치는 필요하지 않습니다."
        )
    folder = Path(__file__).resolve().parent / "vendor" / "windows-cp311-amd64"
    for name in ("numpy", "pygame"):
        if not (folder / name / "__init__.py").is_file():
            raise RuntimeError(
                f"동봉된 {name} 라이브러리를 찾을 수 없습니다. "
                "vendor 폴더를 포함한 프로젝트 전체를 내려받아 압축을 풀어 주세요."
            )
    # 설치된 전역 패키지보다 vendor 패키지가 우선하도록 지정합니다.
    location = str(folder)
    if location in sys.path:
        sys.path.remove(location)
    sys.path.insert(0, location)
    return folder
