import { Github } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-ink/10 bg-paper">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Brand */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="flex h-7 w-7 items-center justify-center rounded-sm border border-ink bg-ink text-white text-xs font-bold font-serif">
                墨
              </div>
              <span className="text-base font-semibold text-ink tracking-tight">
                InkSight
              </span>
            </div>
            <p className="text-sm text-ink-light leading-relaxed">
              一款极简主义的智能电子墨水屏桌面摆件，
              <br />
              通过 LLM 生成有温度的慢信息。
            </p>
          </div>

          {/* Links */}
          <div>
            <h4 className="text-sm font-semibold text-ink mb-3">链接</h4>
            <ul className="space-y-2 text-sm text-ink-light">
              <li>
                <a
                  href="https://github.com/datascale-ai/inksight"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-ink transition-colors inline-flex items-center gap-1.5"
                >
                  <Github size={14} />
                  GitHub 仓库
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/datascale-ai/inksight/blob/main/docs/hardware.md"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-ink transition-colors"
                >
                  硬件指南
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/datascale-ai/inksight/blob/main/docs/api.md"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-ink transition-colors"
                >
                  API 文档
                </a>
              </li>
            </ul>
          </div>

          {/* Tech */}
          <div>
            <h4 className="text-sm font-semibold text-ink mb-3">技术栈</h4>
            <ul className="space-y-2 text-sm text-ink-light">
              <li>ESP32-C3 + 4.2&quot; E-Paper</li>
              <li>Python FastAPI Backend</li>
              <li>DeepSeek / 通义千问 / Kimi</li>
            </ul>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-ink/10 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-ink-light">
            &copy; {new Date().getFullYear()} InkSight. Released under the MIT License.
          </p>
          <p className="text-xs text-ink-light">
            Made with care for slow information.
          </p>
        </div>
      </div>
    </footer>
  );
}
