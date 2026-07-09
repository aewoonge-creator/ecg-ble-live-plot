# ECG BLE Live Plot GUI

AD8608 analog front-end output을 nRF54L15 ADC로 샘플링하고, BLE Notify로 노트북에 보내 실시간 ECG를 확인하는 브라우저 GUI입니다.

이 프로젝트의 우선순위는 **원신호 품질 확인**입니다. 필터링은 회로, 전극, RLD/DRL, 기준전압, 케이블 노이즈를 확인한 뒤에 적용하는 downstream 단계로 두었습니다.

## Features

- Web Bluetooth BLE Notify 수신
- Web Serial USB CDC 수신
- Nordic UART Service UUID 기본값 제공
- ASCII, `uint16`, `int16`, `float32` Notify payload 지원
- ADC count -> voltage 변환
- ADC center, Vref, ADC bits, AD8608 AFE gain 보정
- DC/reference 제거
- real-time HPF 0.5-1 Hz, 60 Hz notch, LPF 40 Hz
- raw input과 filtered ECG 동시 plot
- rough heart-rate estimate
- CSV recording/export
- BLE 장치 없이 실행 가능한 ECG simulator
- 오프라인 CSV 필터/검증용 Python 도구 포함

## Quick Start

```powershell
cd "C:\Users\GC\OneDrive - 가천대학교\문서\애웅이\work\ecg_ble_gui"
python .\serve_gui.py
```

브라우저에서 엽니다.

```text
http://127.0.0.1:8765/gui.html
```

Chrome 또는 Edge를 권장합니다. Web Bluetooth는 보안 정책 때문에 보통 `http://127.0.0.1` 또는 `https`에서 실행해야 합니다.

BLE 장치가 없어도 `시뮬레이터 시작`을 눌러 plot, filter, CSV 저장 기능을 먼저 확인할 수 있습니다.

## Hardware Flow

```text
ECG electrodes
  -> AD8608 analog front-end
  -> nRF54L15 ADC
  -> BLE Notify or USB Serial
  -> laptop browser GUI
  -> ADC conversion + HPF/notch/LPF + live plot
```

권장 실험 순서:

1. AD8608 회로 출력이 오실로스코프에서 포화되지 않는지 확인합니다.
2. 전극 위치, 접촉 임피던스, 케이블 흔들림, RLD/DRL, 기준전압을 먼저 안정화합니다.
3. nRF54L15 ADC raw count가 안정적으로 들어오는지 UART log 또는 nRF Connect로 확인합니다.
4. GUI 시뮬레이터로 화면 동작을 확인합니다.
5. BLE Notify 또는 USB Serial을 연결하고 raw input panel을 먼저 봅니다.
6. raw input이 괜찮을 때 HPF/notch/LPF를 켜고 filtered ECG panel을 해석합니다.

## BLE Defaults

GUI 기본값은 Nordic UART Service입니다.

```text
Service UUID: 6e400001-b5a3-f393-e0a9-e50e24dcca9e
Notify UUID : 6e400003-b5a3-f393-e0a9-e50e24dcca9e
```

nRF firmware에서 다른 custom service/characteristic을 쓰면 GUI 입력칸에서 UUID를 바꾸면 됩니다.

## USB Serial Mode

BLE가 없는 데스크탑에서는 nRF54L15 firmware가 USB CDC serial로 ADC sample을 출력하게 만들면 됩니다. GitHub Pages의 `gui.html`을 Chrome 또는 Edge에서 열고 `USB Serial 연결`을 누르세요.

권장 serial payload:

```text
adc
t_ms,adc
```

예시:

```text
2038
1024,2041
1026,2044
```

함수발생기로 sine을 넣어 ADC/plot 경로만 확인할 때는 `5-10 Hz`, `100-300 mVpp`, ADC 입력 범위 안의 DC offset으로 시작하세요.

## Notify Payload Contract

가장 디버깅하기 쉬운 형식은 ASCII 한 줄입니다.

```text
adc
t_ms,adc
```

예시:

```text
2038
1024,2041
1026,2044
```

속도를 높이고 싶으면 `uint16 little-endian`을 선택하고 Notify payload에 ADC count를 2바이트씩 packed로 보냅니다.

```text
sample0_low, sample0_high, sample1_low, sample1_high, ...
```

자세한 펌웨어 쪽 payload 규격은 [docs/nrf54l15_ble_payload.md](docs/nrf54l15_ble_payload.md)를 참고하세요.

## Filter Settings

기본 필터 순서:

```text
DC/reference removal -> HPF -> 60 Hz notch -> LPF
```

기본값:

- HPF: `0.5 Hz`
- Notch: `60 Hz`, Q `30`
- LPF: `40 Hz`
- sample rate: `500 Hz`

HPF는 baseline wander가 큰 경우 `0.5 Hz`에서 시작하고, 움직임/전극 흔들림이 크면 `1 Hz`까지 올려 비교하세요. 단, ST segment 같은 저주파 정보를 보려는 목적이면 HPF를 너무 높이지 않는 게 좋습니다.

## Offline CSV Filtering

브라우저에서 저장한 CSV나 오실로스코프 CSV를 오프라인으로 다시 필터링할 수 있습니다. 외부 패키지 없이 표준 Python만 사용합니다.

```powershell
python .\tools\filter_ecg_csv.py .\sample.csv --time-col 0 --value-col 1 --hpf 0.5 --notch 60 --lpf 40
```

time column이 없고 500 Hz로 샘플링한 ADC count만 있으면:

```powershell
python .\tools\filter_ecg_csv.py .\adc_only.csv --time-col -1 --value-col 0 --fs 500 --adc-bits 12 --adc-vref 3.3 --adc-center 2048
```

결과는 `outputs/`에 CSV와 SVG로 저장됩니다.

## Repository Layout

```text
ecg_ble_gui/
  index.html                    # GitHub Pages project landing page
  gui.html                      # Web Bluetooth live GUI
  assets/                       # Pages images and plots
  serve_gui.py                  # local no-cache HTTP server
  tools/filter_ecg_csv.py       # offline ECG CSV filter
  docs/nrf54l15_ble_payload.md  # firmware payload contract
  docs/signal_quality_checklist.md
  .gitignore
```

## GitHub Upload

이 폴더에서 Git이 설치된 터미널을 열고:

```powershell
git init
git add .
git commit -m "Initial ECG BLE live plot GUI"
git branch -M main
git remote add origin https://github.com/YOUR_ID/ecg-ble-live-plot.git
git push -u origin main
```

현재 Codex 환경에서는 `git` 명령이 PATH에 없으면 직접 push가 안 됩니다. Git for Windows를 설치했거나 GitHub Desktop을 쓰면 이 폴더를 그대로 새 repository로 올리면 됩니다.

## Safety Note

이 GUI와 필터는 연구/학습용입니다. 의료 진단용으로 사용하면 안 됩니다. 사람 몸에 연결하는 회로는 배터리 구동, 절연, 전류 제한, ESD/입력 보호를 우선 확인하세요.
