# 동봉 라이브러리

`windows-cp311-amd64/`는 **Windows x64용 CPython 3.11(64비트)**에서 사용하는 NumPy 2.2.6과 Pygame 2.6.1입니다. PyPI의 공식 Windows wheel을 원래 구조 그대로 압축 해제했습니다. 실행 시 `vendor_loader.py`가 이 폴더를 import 경로의 맨 앞에 추가합니다. 다운로드·설치·압축 해제 작업은 실행 중에 필요하지 않습니다.

공식 PyPI SHA-256과 wheel 내부 RECORD 해시를 검증한 배포 파일을 사용했습니다. 원본 파일명, 다운로드 출처와 SHA-256은 `manifest.json`에 기록했습니다. 라이선스와 제삼자 고지, `.dist-info`와 DLL을 함께 보존했습니다. 공급 라이브러리의 내부 코드와 주석은 원본 그대로입니다.

이 바이너리는 다른 Python 버전, Windows ARM64/32비트 또는 Linux/macOS용이 아닙니다. 해당 환경에서는 동일 바이너리를 재사용할 수 없습니다. 프로젝트의 실험 코드와 설정은 기존 그대로 사용합니다.
