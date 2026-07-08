# ECG Raw Signal Quality Checklist

필터를 켜기 전에 raw input panel에서 먼저 확인할 항목입니다.

## Analog Front-End

- AD8608 출력이 ADC range 안에 들어오는가?
- 출력이 rail에 붙어서 포화되지 않는가?
- 기준전압/mid-supply가 안정적인가?
- AFE gain이 ECG amplitude에 비해 너무 크거나 작지 않은가?
- 입력 보호와 bias path가 구성되어 있는가?

## Electrode and Cable

- 전극 접촉이 안정적인가?
- 전극 위치를 바꿨을 때 QRS가 더 잘 보이는 조합이 있는가?
- 케이블을 움직일 때 baseline이 크게 흔들리지 않는가?
- loop area를 줄이고 전원/USB/노트북 충전기 노이즈를 줄였는가?

## RLD/DRL

- RLD/DRL을 켰을 때 common-mode noise가 줄어드는가?
- RLD/DRL 때문에 발진하거나 포화되지 않는가?
- 회로가 불안하면 RLD/DRL gain을 낮춰 비교했는가?

## Digital Side

- ADC sample rate가 GUI sample rate와 같은가?
- ADC bits, Vref, ADC center가 실제 firmware 설정과 같은가?
- BLE packet loss가 심하지 않은가?
- raw input에서 QRS 후보가 보인 뒤 HPF/notch/LPF를 켰는가?

## Decision Gate

- raw input에서 QRS가 대략 보이면: filter tuning, BLE 안정성, CSV 저장으로 진행
- raw input이 포화/흔들림/60 Hz 지배이면: 회로, 전극, RLD/DRL, 케이블을 먼저 수정
