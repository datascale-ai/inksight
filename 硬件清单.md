# InkSight 硬件购买清单与方案推荐

为了方便大家复现项目，我们整理了三种主流的硬件购买方案（与视频介绍同步）。所有方案均基于 **ESP32-C3** 或 **ESP32** 芯片与 **4.2寸墨水屏**。

---

## 方案一：分体式组装（适合新手，接线明确，最便宜）
最经典的 DIY 方案：买一块标准的 ESP32-C3 开发板，加一块屏幕驱动板，再买一块裸屏，用杜邦线连起来。

| 硬件名称 | 规格/说明 | 购买链接 |
| :--- | :--- | :--- |
| **ESP32-C3 开发板** | 标准板（已焊接排针），带串口芯片调试稳定 | [点击购买](https://e.tb.cn/h.i9BDn7WfeCJ6tMj?tk=Ywg95W7WhC6) |
| **屏幕驱动板** | 用于连接裸屏和 ESP32 | [点击购买](https://e.tb.cn/h.ikOdgh7chlaSHGX?tk=jWnQ5W7Y8Q6) |
| **4.2寸墨水屏（裸屏）** | 选一家即可。中景园/微雪（黑白），或大连佳显（黑白红黄四色） | 1. [中景园电子](https://e.tb.cn/h.i9BCcUbwnwWAAOJ?tk=n3gk5W7VnSL)<br>2. [微雪电子](https://e.tb.cn/h.ikOTSm8WK3PyJY2?tk=6aOk5W74xU4)<br>3. [大连佳显(四色)](https://e.tb.cn/h.iP327lHxszfRGYs?tk=SFah5W78CIM) |
| **杜邦线** | 母对母，用于连接主板和驱动板 | [点击购买](https://e.tb.cn/h.ikO8Tx1kMIpqLV9?tk=rdGf5W77aIV) |

---

## 方案二：一体化驱动板方案（走线最少，最整洁）
直接购买板载了 ESP32 芯片的屏幕驱动板，省去了主板和驱动板之间的杜邦线飞线，只需插上裸屏排线即可。

| 硬件名称 | 规格/说明 | 购买链接 |
| :--- | :--- | :--- |
| **带 ESP32 的屏幕驱动板** | 驱动板上自带 ESP32 芯片，高度集成 | [点击购买](https://e.tb.cn/h.i9zVIhwdYt9APAF?tk=PMx85W79i4A) |
| **4.2寸墨水屏（裸屏）** | 同方案一，选一家即可 | 1. [中景园电子](https://e.tb.cn/h.i9BCcUbwnwWAAOJ?tk=n3gk5W7VnSL)<br>2. [微雪电子](https://e.tb.cn/h.ikOTSm8WK3PyJY2?tk=6aOk5W74xU4)<br>3. [大连佳显(四色)](https://e.tb.cn/h.iP327lHxszfRGYs?tk=SFah5W78CIM) |

---

## 方案三：屏幕模块方案（体积紧凑，屏幕模块更不易损坏软排线）
购买已经把驱动电路和屏幕集成在一起的“屏幕模块”，再搭配一块体积小巧的 ESP32-C3 Pro mini。

| 硬件名称 | 规格/说明 | 购买链接 |
| :--- | :--- | :--- |
| **ESP32-C3 开发板** | Pro mini（体积极小）或 方案一中的标准板 | [Pro mini 购买链接](https://e.tb.cn/h.ikOmTcBXDkJ0XtL?tk=oEzS5W7PU1b) |
| **4.2寸屏幕模块** | 微雪 4.2寸模块（屏幕与驱动板已集成在一起） | [点击购买](https://e.tb.cn/h.i9z5AukJXypr2rU?tk=akUd5W7OEwA) |
| **杜邦线** | 母对母，用于连接主板和屏幕模块 | [点击购买](https://e.tb.cn/h.ikO8Tx1kMIpqLV9?tk=rdGf5W77aIV) |

---

### 可选配件（供电方案）
如果你想让设备脱离电源线运行，可以增加锂电池：
- **软包锂电池**：推荐 `505060-2000mAh`，[电池链接](https://e.tb.cn/h.ie9YjldeSqtOg3z?tk=6vgZUvwh0UE)
- **充电模块**：TP5000 Type-C 充电模块，[充电模块链接](https://item.taobao.com/item.htm?id=822305558260&mi_id=0000ld33KA5E9GmNJ28axUJHtNT-7VQgdCzFcXBL0JTDUnE&spm=tbpc.boughtlist.suborder_itemtitle.1.3dc22e8dyywV7i)
