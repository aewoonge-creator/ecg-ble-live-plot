# nRF54L15 BLE Payload Contract

이 문서는 nRF54L15 firmware와 `index.html` GUI 사이의 데이터 계약입니다.

## Recommended BLE Service

처음에는 Nordic UART Service를 쓰면 디버깅이 쉽습니다.

```text
Service UUID: 6e400001-b5a3-f393-e0a9-e50e24dcca9e
TX Notify  : 6e400003-b5a3-f393-e0a9-e50e24dcca9e
```

GUI의 `Service UUID`, `Notify characteristic UUID` 입력칸을 firmware와 맞추면 됩니다.

## Sampling

권장 시작값:

- ADC sampling rate: `500 Hz`
- ADC resolution: `12 bit`
- ADC reference: firmware 설정값에 맞춤
- payload block: 10-20 samples per notification

BLE notification을 sample마다 하나씩 보내면 overhead가 큽니다. 가능하면 여러 ADC sample을 한 notification에 묶으세요.

## Payload Option 1: ASCII

가장 먼저 추천하는 디버깅 형식입니다.

```text
adc\n
t_ms,adc\n
```

예시:

```text
2040\n
1024,2042\n
1026,2045\n
```

장점:

- nRF Connect에서 바로 읽을 수 있음
- CSV/log와 비교하기 쉬움
- timestamp drift 확인 가능

단점:

- binary보다 전송 효율 낮음

## Payload Option 2: uint16 little-endian

GUI `Notify payload`를 `Binary: uint16 little-endian`으로 선택합니다.

```text
uint16 sample0
uint16 sample1
uint16 sample2
...
```

byte order:

```text
sample_low_byte, sample_high_byte
```

12-bit ADC라도 16-bit container에 담아서 보냅니다.

## Payload Option 3: int16 or float32

ADC driver 또는 firmware filter에서 signed value나 voltage value로 바꿔 보내고 싶을 때 씁니다.

- `int16 little-endian`: signed ADC-like samples
- `float32 little-endian`: voltage unit sample로 취급

초기 실험에서는 raw ADC count를 보내는 편이 좋습니다. GUI에서 Vref, center, gain을 바꾸며 해석할 수 있기 때문입니다.

## Firmware Pseudocode

```c
static uint16_t block[16];
static size_t count;

void adc_sample_ready(uint16_t adc_count)
{
    block[count++] = adc_count;

    if (count == 16) {
        ble_notify(tx_char, (uint8_t *)block, sizeof(block));
        count = 0;
    }
}
```

실제 Zephyr/NCS project에서는 `bt_gatt_notify` 또는 NUS helper API에 해당 byte buffer를 넘기면 됩니다.

## Bring-up Checklist

1. ADC pin이 AD8608 출력 범위를 넘지 않는지 확인합니다.
2. ADC center가 GUI `ADC center`와 맞는지 확인합니다.
3. nRF Connect 앱으로 Notify가 실제로 나오는지 확인합니다.
4. GUI simulator가 정상인지 확인합니다.
5. GUI BLE 연결 후 raw input부터 확인합니다.
