# Hardware BOM & Purchasing Schemes

To make sourcing parts easier, we've organized three mainstream hardware purchasing schemes. All schemes are based on the **ESP32-C3** or **ESP32** chip paired with a **4.2-inch e-paper display**.

> **Note for international builders:** The links below are for **Taobao** (China). If you are buying from outside China, please search for equivalent parts on **AliExpress** or **Amazon** using the part names.

---

## Scheme 1: Component Assembly (Best for Beginners, Clear Wiring)
The classic DIY approach: buy a standard ESP32-C3 dev board, a display driver board, and a bare e-paper screen, then connect them with Dupont wires.

| Part | Description | Taobao Link (Reference) |
| :--- | :--- | :--- |
| **ESP32-C3 Dev Board** | Standard board (pre-soldered pins) with a dedicated serial chip for stable debugging | [Link](https://e.tb.cn/h.i9BDn7WfeCJ6tMj?tk=Ywg95W7WhC6) |
| **Display Driver Board** | Used to connect the bare screen to the ESP32 | [Link](https://e.tb.cn/h.ikOdgh7chlaSHGX?tk=jWnQ5W7Y8Q6) |
| **4.2-inch E-paper (Bare Screen)** | Zhongjingyuan / Waveshare (B/W), or Dalian Good Display (B/W/R/Y 4-color) | 1. [Zhongjingyuan](https://e.tb.cn/h.i9BCcUbwnwWAAOJ?tk=n3gk5W7VnSL)<br>2. [Waveshare](https://e.tb.cn/h.ikOTSm8WK3PyJY2?tk=6aOk5W74xU4)<br>3. [Good Display (4-color)](https://e.tb.cn/h.iP327lHxszfRGYs?tk=SFah5W78CIM) |
| **Dupont Wires** | Female-to-Female | [Link](https://e.tb.cn/h.ikO8Tx1kMIpqLV9?tk=rdGf5W77aIV) |

---

## Scheme 2: Integrated Driver Board (Cleanest Wiring)
Buy a display driver board that has the ESP32 chip built-in. This eliminates the need for Dupont wires between the MCU and driver board—just plug in the screen's ribbon cable.

| Part | Description | Taobao Link (Reference) |
| :--- | :--- | :--- |
| **Integrated ESP32 Driver Board** | Highly integrated board with onboard ESP32 | [Link](https://e.tb.cn/h.i9zVIhwdYt9APAF?tk=PMx85W79i4A) |
| **4.2-inch E-paper (Bare Screen)** | Same as Scheme 1 | 1. [Zhongjingyuan](https://e.tb.cn/h.i9BCcUbwnwWAAOJ?tk=n3gk5W7VnSL)<br>2. [Waveshare](https://e.tb.cn/h.ikOTSm8WK3PyJY2?tk=6aOk5W74xU4)<br>3. [Good Display (4-color)](https://e.tb.cn/h.iP327lHxszfRGYs?tk=SFah5W78CIM) |

---

## Scheme 3: Screen Module (Most Compact)
Buy a "screen module" (where the driver circuit is integrated onto the back of the screen) and pair it with a tiny ESP32-C3 Pro mini. Perfect for building ultra-thin cases.

| Part | Description | Taobao Link (Reference) |
| :--- | :--- | :--- |
| **ESP32-C3 Dev Board** | Pro mini (extremely small) or the standard board from Scheme 1 | [Pro mini Link](https://e.tb.cn/h.ikOmTcBXDkJ0XtL?tk=oEzS5W7PU1b) |
| **4.2-inch Screen Module** | Waveshare 4.2-inch module (screen and driver board integrated) | [Link](https://e.tb.cn/h.i9z5AukJXypr2rU?tk=akUd5W7OEwA) |
| **Dupont Wires** | Female-to-Female | [Link](https://e.tb.cn/h.ikO8Tx1kMIpqLV9?tk=rdGf5W77aIV) |

---

### Optional Power Accessories
If you want the device to run without a USB cable, you can add a lithium battery:
- **Lithium Battery**: Pouch `505060-2000mAh`, [Link](https://e.tb.cn/h.ie9YjldeSqtOg3z?tk=6vgZUvwh0UE)
- **Charger Module**: TP5000 Type-C charging module, [Link](https://item.taobao.com/item.htm?id=822305558260&mi_id=0000ld33KA5E9GmNJ28axUJHtNT-7VQgdCzFcXBL0JTDUnE&spm=tbpc.boughtlist.suborder_itemtitle.1.3dc22e8dyywV7i)
