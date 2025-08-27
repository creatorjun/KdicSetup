<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KdicSetup - GUI PC 초기화 자동화 프로그램</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 20px auto;
            padding: 0 20px;
            background-color: #f9f9f9;
        }
        h1, h2, h3 {
            color: #2c3e50;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 10px;
        }
        h1 {
            font-size: 2.5em;
            text-align: center;
        }
        h2 {
            font-size: 2em;
            margin-top: 40px;
        }
        h3 {
            font-size: 1.5em;
            margin-top: 30px;
        }
        p {
            margin-bottom: 15px;
        }
        ul, ol {
            padding-left: 20px;
        }
        li {
            margin-bottom: 10px;
        }
        code {
            background-color: #ecf0f1;
            padding: 2px 5px;
            border-radius: 4px;
            font-family: "Courier New", Courier, monospace;
        }
        pre {
            background-color: #2c3e50;
            color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            white-space: pre-wrap;
        }
        pre code {
            background-color: transparent;
            padding: 0;
        }
        .container {
            background-color: #ffffff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        nav {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 30px;
        }
        nav h3 {
            margin-top: 0;
            border-bottom: none;
        }
        nav ol {
            list-style-type: none;
            padding-left: 0;
        }
        nav ol li a {
            text-decoration: none;
            color: #3498db;
        }
        nav ol li a:hover {
            text-decoration: underline;
        }
        details {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 4px;
            padding: 10px;
            margin-bottom: 15px;
        }
        summary {
            cursor: pointer;
            font-weight: bold;
            color: #2980b9;
        }
        .center-image {
            display: block;
            margin-left: auto;
            margin-right: auto;
            max-width: 100%;
            height: auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>KdicSetup - GUI PC 초기화 자동화 프로그램</h1>
        <p>KdicSetup은 Windows PC의 포맷, 운영체제 설치, 드라이버 및 기본 설정까지의 복잡한 초기화 과정을 자동화하는 PyQt6 기반의 GUI 애플리케이션입니다. 사용자는 간단한 UI를 통해 원하는 옵션을 선택하고 클릭 한 번으로 PC 설정을 완료할 수 있습니다.</p>

        <nav>
            <h3>목차</h3>
            <ol>
                <li><a href="#features">주요 기능</a></li>
                <li><a href="#requirements">실행 환경 및 사전 요구사항</a></li>
                <li><a href="#usage">사용 방법</a></li>
                <li><a href="#architecture">아키텍처</a></li>
                <li><a href="#structure">프로젝트 구조</a></li>
                <li><a href="#components">핵심 컴포넌트 상세</a></li>
                <li><a href="#maintenance">유지보수 가이드</a></li>
            </ol>
        </nav>

        <section id="features">
            <h2>1. 주요 기능</h2>
            <ul>
                <li>🖥️ <strong>사용자 친화적 GUI:</strong> 직관적인 인터페이스로 모든 작업을 쉽게 제어할 수 있습니다.</li>
                <li>🔍 <strong>자동 시스템 분석:</strong> 프로그램 시작 시 디스크, 볼륨, 메인보드 등 하드웨어 정보를 자동으로 분석합니다.</li>
                <li>⚙️ <strong>맞춤형 초기화:</strong> PC 용도(내부망, 인터넷, 출장용 등)에 따른 맞춤형 이미지 설치를 지원합니다.</li>
                <li>💾 <strong>데이터 보존 옵션:</strong> 사용자 데이터를 삭제하지 않고 운영체제만 안전하게 재설치할 수 있습니다.</li>
                <li>🚀 <strong>완전 자동화:</strong> 포맷, 이미지 적용(WIM), 드라이버 설치, 부팅 구성까지 모든 과정을 자동으로 수행합니다.</li>
                <li>📊 <strong>실시간 피드백:</strong> 진행률 표시줄, 예상 남은 시간, 상세 로그를 통해 작업 현황을 실시간으로 확인할 수 있습니다.</li>
            </ul>
        </section>

        <section id="requirements">
            <h2>2. 실행 환경 및 사전 요구사항</h2>
            <h3>2.1. 실행 환경</h3>
            <ul>
                <li><strong>운영체제:</strong> Windows 10 이상</li>
                <li><strong>필수 라이브러리:</strong>
                    <ul>
                        <li>PyQt6</li>
                        <li>wmi</li>
                        <li>pywin32</li>
                    </ul>
                </li>
            </ul>
            <h3>2.2. 사전 요구사항</h3>
            <ul>
                <li><strong>관리자 권한:</strong> <code>diskpart</code>, <code>DISM</code> 등 시스템 명령어를 사용하므로 반드시 관리자 권한으로 실행해야 합니다.</li>
                <li><strong>폴더 구조:</strong> 프로그램이 올바르게 동작하려면 아래와 같은 폴더 구조를 유지해야 합니다.
                    <pre><code>/C:/KdicSetup/  (&lt;- 루트 폴더)
├── KdicSetup/      
│   ├── KdicSetup.exe  (&lt;- 실행 파일)
│   └── ...
├── wim/
│   ├── work.wim
│   ├── internet.wim
│   └── ...
└── Drivers/
    ├── P8H61-M-PRO-ASUS-2103/ (&lt;- 메인보드 모델명)
    │   ├── ... (드라이버 파일들) ...
    └── ...</code></pre>
                </li>
            </ul>
        </section>

        <section id="usage">
            <h2>3. 사용 방법</h2>
            <ol>
                <li><code>KdicSetup.exe</code>를 관리자 권한으로 실행합니다.</li>
                <li>프로그램이 자동으로 시스템을 분석할 때까지 잠시 기다립니다.</li>
                <li><strong>[타입 선택]</strong> 에서 원하는 PC 용도를 선택합니다.</li>
                <li><strong>[데이터 보존]</strong> 여부를 선택합니다. (환경에 따라 비활성화될 수 있음)</li>
                <li><strong>[시작]</strong> 버튼을 클릭합니다.
                    <ul>
                        <li>'데이터 보존'을 선택하지 않은 경우, 데이터 삭제 확인을 위해 암호(<code>960601</code>)를 입력해야 합니다.</li>
                    </ul>
                </li>
                <li>자동으로 작업이 진행되며, 완료 후 재부팅 확인 창이 나타납니다.</li>
                <li>확인 시 10초 후 자동으로 재부팅됩니다.</li>
            </ol>
        </section>

        <section id="architecture">
            <h2>4. 아키텍처</h2>
            <p>본 프로그램은 <strong>MVC(Model-View-Controller) 패턴</strong>을 기반으로 하며, UI 반응성을 유지하기 위해 <strong>멀티스레딩</strong>을 사용합니다.</p>
            <ul>
                <li><strong>View (view.py):</strong> 사용자 인터페이스(UI)를 담당하며, 사용자 입력을 Controller로 전달합니다.</li>
                <li><strong>Controller (controller.py):</strong> View와 백그라운드 작업(Model, Worker) 간의 상호작용을 제어하는 중재자 역할을 합니다.</li>
                <li><strong>Model (models.py):</strong> <code>Options</code>, <code>SystemInfo</code> 등 프로그램에서 사용하는 데이터 구조를 정의합니다.</li>
                <li><strong>Background Threads (loader.py, worker.py):</strong> 시스템 분석 및 PC 초기화처럼 시간이 오래 걸리는 작업을 별도의 스레드에서 처리하여 UI 멈춤 현상을 방지합니다.</li>
            </ul>
            <img src="https://i.imgur.com/k9b3B0G.png" alt="Architecture Diagram" class="center-image" width="700">
        </section>

        <section id="structure">
            <h2>5. 프로젝트 구조</h2>
            <pre><code>KdicSetup/
├── KdicSetup.py         # 메인 실행 파일 (Entry Point)
├── view.py              # UI 로직
├── controller.py        # 메인 제어 로직
├── loader.py            # 시스템 분석 스레드
├── worker.py            # 실제 작업 수행 스레드
├── models.py            # 데이터 모델 (dataclasses)
├── utils.py             # 유틸리티 함수 (명령어 실행 등)
├── dialog.py            # 사용자 확인 대화상자
├── logger.py            # 로깅 시스템 설정
└── .gitignore           # Git 버전 관리 제외 목록</code></pre>
        </section>

        <section id="components">
            <h2>6. 핵심 컴포넌트 상세</h2>
            <details>
                <summary><b>Loader.py - 시스템 분석기</b></summary>
                <ul>
                    <li><code>diskpart</code> 명령으로 디스크 및 볼륨 정보를 수집합니다.</li>
                    <li>USB 디스크를 제외하고, 폴더 구조를 기반으로 System, Data, Boot 볼륨을 자동으로 분류합니다.</li>
                    <li>WMI를 통해 메인보드 모델명을 조회하고, <code>../Drivers/</code> 에서 일치하는 드라이버 폴더 경로를 찾습니다.</li>
                    <li>분석된 모든 정보를 <code>SystemInfo</code> 객체에 담아 Controller로 전달합니다.</li>
                </ul>
            </details>
            <details>
                <summary><b>Worker.py - 자동화 작업자</b></summary>
                <ul>
                    <li>사용자 옵션에 따라 <code>diskpart</code> 스크립트를 동적으로 생성하여 디스크 포맷 및 파티션 생성을 수행합니다.</li>
                    <li><code>DISM</code> 명령으로 선택된 WIM 이미지를 OS 파티션에 적용하고, 드라이버를 통합 설치합니다.</li>
                    <li><code>robocopy</code>를 이용해 사용자 폴더 등 기타 설정 파일들을 복원합니다.</li>
                    <li><code>bcdboot</code>, <code>bcdedit</code> 명령으로 UEFI 부팅 정보를 구성합니다.</li>
                </ul>
            </details>
            <details>
                <summary><b>Controller.py - 중앙 통제 장치</b></summary>
                <ul>
                    <li>View로부터의 사용자 입력(시그널)을 받아 Loader나 Worker 스레드를 시작/중지시킵니다.</li>
                    <li>Loader와 Worker로부터 진행률, 로그, 완료/오류 상태를 받아 View에 업데이트합니다.</li>
                    <li>작업 완료 후 실제 소요 시간을 파일에 저장하여 다음 실행 시 '예상 남은 시간'의 정확도를 높입니다.</li>
                </ul>
            </details>
        </section>

        <section id="maintenance">
            <h2>7. 유지보수 가이드</h2>
            <h3>7.1. WIM 이미지 관리</h3>
            <ul>
                <li><strong>경로:</strong> <code>../wim/</code></li>
                <li>PC 타입 추가 또는 이미지 업데이트 시, 해당 폴더에 <code>.wim</code> 파일을 추가/교체하세요.</li>
                <li><strong>코드 수정:</strong> 새 타입을 추가하는 경우, <code>worker.py</code>의 <code>wim_map</code>과 <code>view.py</code>의 <code>buttons</code> 딕셔너리를 수정해야 합니다.</li>
            </ul>
            <h3>7.2. 드라이버 관리</h3>
            <ul>
                <li><strong>경로:</strong> <code>../Drivers/</code></li>
                <li>새 PC 모델의 드라이버를 추가하려면, <code>[메인보드 모델명]</code>으로 시작하는 폴더를 생성하고 내부에 드라이버 파일을 위치시키세요.</li>
                <li><strong>참고:</strong> 모델명은 WMI 조회 결과와 일치해야 정확히 인식됩니다.</li>
            </ul>
            <h3>7.3. 디버깅</h3>
            <ul>
                <li>프로그램 실행 시 생성되는 <code>log.txt</code> 파일을 확인하면 모든 작업의 상세 과정과 오류 내역을 파악할 수 있습니다.</li>
            </ul>
            <h3>7.4. 설정 변경</h3>
            <ul>
                <li><strong>데이터 삭제 확인 암호:</strong> <code>dialog.py</code>의 <code>ConfirmationDialog</code> 클래스 내 <code>_validate_input</code> 메소드에서 변경할 수 있습니다.</li>
                <li><strong>기본 예상 시간:</strong> <code>controller.py</code>의 <code>start_automation</code> 메소드에서 디스크 타입별(NVMe, SSD, HDD) 기본 예상 시간을 조정할 수 있습니다.</li>
            </ul>
        </section>
    </div>
</body>
</html>
