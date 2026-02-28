import Link from "next/link";
import { Lightbulb, Zap } from "lucide-react";

export default function DocsPage() {
  return (
    <article className="docs-prose">
      {/* H1 */}
      <h1>快速开始</h1>

      {/* Blockquote */}
      <blockquote>
        InkSight 是一个完全开源的智能电子墨水屏桌面摆件项目。只需简单几步，你就能拥有一台由
        AI 驱动的「慢信息」显示终端 —— 不推送焦虑，只呈现有温度的内容。
      </blockquote>

      <p>
        本文档将引导你完成从硬件组装到固件烧录的完整流程。整个过程大约需要 30
        分钟，无需任何编程基础。
      </p>

      {/* H2 */}
      <h2>1. 硬件准备</h2>

      <p>
        你需要准备以下硬件，全部可以在淘宝或 AliExpress 上购买到，总成本不超过
        220 元：
      </p>

      {/* Unordered List */}
      <ul>
        <li>
          <strong>ESP32-C3 SuperMini 开发板</strong> — RISC-V 架构，内置
          WiFi，超低功耗，约 20 元
        </li>
        <li>
          <strong>4.2 英寸电子墨水屏 (SPI 接口)</strong> — 400&times;300
          分辨率，SSD1683 驱动，约 110 元。也支持 2.9&quot;(296&times;128)、5.83&quot;(648&times;480)、7.5&quot;(800&times;480) 等尺寸
        </li>
        <li>
          <strong>USB-C 数据线</strong> — 用于供电和固件烧录（确保支持数据传输）
        </li>
        <li>
          <strong>杜邦线 6 根</strong> — 连接开发板和墨水屏的 SPI 信号线
        </li>
        <li>
          <strong>LiFePO4 电池 + TP5000 充电模块</strong>{" "}
          （可选）— 实现无线供电，续航约 6 个月
        </li>
      </ul>

      {/* Callout - Tip */}
      <div className="callout callout-tip">
        <div className="callout-icon">
          <Lightbulb size={16} />
        </div>
        <div>
          <p className="callout-title">硬件购买建议</p>
          <p>
            ESP32-C3 SuperMini 是目前性价比最高的选择。购买墨水屏时注意选择
            <strong>SPI 接口</strong>版本（非 I2C），驱动芯片为 SSD1683 或
            IL0398。详细的引脚接线图请参考{" "}
            <Link href="/docs/hardware">硬件清单</Link> 页面。
          </p>
        </div>
      </div>

      <h2>2. 固件烧录</h2>

      <p>
        InkSight 支持两种固件烧录方式：<strong>Web 在线刷机</strong>
        （推荐）和传统的命令行烧录。
      </p>

      <h3>方式一：Web 在线刷机（推荐）</h3>

      <p>
        这是最简单的方式，无需安装任何软件。只需一根 USB 线和 Chrome 浏览器：
      </p>

      {/* Callout - Important */}
      <div className="callout callout-important">
        <div className="callout-icon">
          <Zap size={16} />
        </div>
        <div>
          <p className="callout-title">推荐方式</p>
          <p>
            推荐使用官网的{" "}
            <Link href="/flash">Web Flasher</Link>{" "}
            进行一键刷机。现在支持从 GitHub Releases 动态选择固件版本，并可手动刷新版本列表后再刷写。
          </p>
        </div>
      </div>

      <ul>
        <li>浏览器要求：Chrome / Edge 89+（需支持 WebSerial）</li>
        <li>访问要求：必须在 HTTPS 域名或 localhost 下使用</li>
        <li>故障恢复：若版本列表加载失败，可在刷机页点击“刷新版本”重试</li>
        <li>兜底方式：可切换“手动 URL”并先执行链接校验，再刷写 `.bin` 固件</li>
      </ul>

      <h3>方式二：命令行烧录</h3>

      <p>如果你更喜欢使用命令行，或者需要开发自定义固件：</p>

      {/* Code Block */}
      <div className="code-block">
        <div className="code-header">
          <span>Terminal</span>
        </div>
        <pre>
          <code>{`# 克隆项目仓库
git clone https://github.com/datascale-ai/inksight.git
cd inksight/firmware

# 使用 PlatformIO 编译并上传固件
pio run --target upload

# 查看串口日志（验证固件运行正常）
pio device monitor`}</code>
        </pre>
      </div>

      <p>
        如果你使用 Arduino IDE，也可以直接打开{" "}
        <code>firmware/src/main.cpp</code> 进行编译上传。
      </p>

      <h2>3. WiFi 配网</h2>

      <p>固件烧录完成后，设备会自动进入配网模式：</p>

      <ol>
        <li>
          设备启动后，会创建一个名为 <code>InkSight-XXXXXX</code> 的 WiFi
          热点
        </li>
        <li>用手机连接该热点，系统会自动弹出配置页面</li>
        <li>选择你的家庭 WiFi 网络，输入密码</li>
        <li>配置完成后，设备会自动连接网络并开始工作</li>
      </ol>

      <h2>4. 后端部署</h2>

      <p>InkSight 需要一个后端服务来生成内容。你可以选择自托管或使用 Vercel 部署：</p>

      <div className="code-block">
        <div className="code-header">
          <span>Terminal</span>
        </div>
        <pre>
          <code>{`cd inksight/backend

# 安装 Python 依赖
pip install -r requirements.txt

# 下载字体文件（约 70MB）
python scripts/setup_fonts.py

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 LLM API Key

# 启动服务
python -m uvicorn api.index:app --host 0.0.0.0 --port 8080`}</code>
        </pre>
      </div>

      <p>
        服务启动后，访问{" "}
        <code>http://localhost:8080</code> 即可看到预览控制台。详细配置请参考{" "}
        <Link href="/docs/api-key">配置 API Key</Link> 章节。
      </p>

      {/* Divider */}
      <hr />

      <p>
        恭喜！你的 InkSight 已经可以正常工作了。接下来可以通过{" "}
        <Link href="/docs/config">Web 配置后台</Link>{" "}
        自定义内容模式、刷新策略和显示风格。
      </p>
    </article>
  );
}
