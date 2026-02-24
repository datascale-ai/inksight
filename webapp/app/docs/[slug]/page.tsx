import path from "node:path";
import { promises as fs } from "node:fs";
import { notFound } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type DocConfig = {
  title: string;
  file?: string;
  fallback?: string;
};

const DOCS: Record<string, DocConfig> = {
  hardware: { title: "硬件清单", file: "hardware.md" },
  assembly: { title: "组装指南", file: "assembly.md" },
  flash: { title: "Web 在线刷机", file: "flash.md" },
  "api-key": { title: "配置 API Key", file: "api-key.md" },
  config: { title: "Web 配置后台", file: "config.md" },
  "plugin-dev": { title: "插件开发", file: "plugin-dev.md" },
  "api-reference": { title: "API 参考", file: "api.md" },
  faq: { title: "常见问题", file: "faq.md" },
};

async function readDocMarkdown(fileName: string): Promise<string | null> {
  try {
    const filePath = path.resolve(process.cwd(), "..", "docs", fileName);
    return await fs.readFile(filePath, "utf-8");
  } catch {
    return null;
  }
}

export default async function DocSlugPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const cfg = DOCS[slug];
  if (!cfg) notFound();

  const markdown = cfg.file ? await readDocMarkdown(cfg.file) : null;
  const content = markdown || cfg.fallback || `# ${cfg.title}\n\n内容建设中。`;

  return (
    <article className="docs-prose">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </article>
  );
}
