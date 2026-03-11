"use client";

import { Cpu } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/config/shared";

export function LlmProviderConfig({
  tr,
  llmProvider,
  setLlmProvider,
  llmModel,
  setLlmModel,
  imageProvider,
  setImageProvider,
  imageModel,
  setImageModel,
  llmApiKey,
  setLlmApiKey,
  imageApiKey,
  setImageApiKey,
  hasApiKey,
  hasImageApiKey,
  llmModels,
  imageModels,
}: {
  tr: (zh: string, en: string) => string;
  llmProvider: string;
  setLlmProvider: (value: string) => void;
  llmModel: string;
  setLlmModel: (value: string) => void;
  imageProvider: string;
  setImageProvider: (value: string) => void;
  imageModel: string;
  setImageModel: (value: string) => void;
  llmApiKey: string;
  setLlmApiKey: (value: string) => void;
  imageApiKey: string;
  setImageApiKey: (value: string) => void;
  hasApiKey: boolean;
  hasImageApiKey: boolean;
  llmModels: Record<string, { v: string; n: string }[]>;
  imageModels: Record<string, { v: string; n: string }[]>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Cpu size={18} /> {tr("AI 模型", "AI Models")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Field label={tr("文本模型服务商", "Text model provider")}>
          <select
            value={llmProvider}
            onChange={(e) => {
              const next = e.target.value;
              setLlmProvider(next);
              setLlmModel(llmModels[next]?.[0]?.v || "");
            }}
            className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
          >
            <option value="deepseek">DeepSeek</option>
            <option value="aliyun">{tr("阿里百炼", "Alibaba Bailian")}</option>
            <option value="moonshot">{tr("月之暗面 (Kimi)", "Moonshot (Kimi)")}</option>
          </select>
        </Field>
        <Field label={tr("文本模型", "Text model")}>
          <select
            value={llmModel}
            onChange={(e) => setLlmModel(e.target.value)}
            className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
          >
            {(llmModels[llmProvider] || []).map((model) => (
              <option key={model.v} value={model.v}>
                {model.n}
              </option>
            ))}
          </select>
        </Field>
        <Field label={tr("文本 API Key", "Text API Key")}>
          <input
            type="password"
            value={llmApiKey}
            onChange={(e) => setLlmApiKey(e.target.value)}
            placeholder={
              hasApiKey
                ? tr("已配置，留空不修改", "Configured, leave empty to keep")
                : tr(
                    "可选，设备专用 Key，留空使用服务器默认",
                    "Optional device-level key, leave empty to use server default",
                  )
            }
            className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white font-mono"
            autoComplete="off"
          />
        </Field>
        <Field label={tr("图像模型服务商", "Image model provider")}>
          <select
            value={imageProvider}
            onChange={(e) => {
              const next = e.target.value;
              setImageProvider(next);
              setImageModel(imageModels[next]?.[0]?.v || "");
            }}
            className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
          >
            <option value="aliyun">{tr("阿里百炼", "Alibaba Bailian")}</option>
          </select>
        </Field>
        <Field label={tr("图像模型", "Image model")}>
          <select
            value={imageModel}
            onChange={(e) => setImageModel(e.target.value)}
            className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white"
          >
            {(imageModels[imageProvider] || []).map((model) => (
              <option key={model.v} value={model.v}>
                {model.n}
              </option>
            ))}
          </select>
        </Field>
        <Field label={tr("图像 API Key", "Image API Key")}>
          <input
            type="password"
            value={imageApiKey}
            onChange={(e) => setImageApiKey(e.target.value)}
            placeholder={
              hasImageApiKey
                ? tr("已配置，留空不修改", "Configured, leave empty to keep")
                : tr(
                    "可选，设备专用 Key，留空使用服务器默认",
                    "Optional device-level key, leave empty to use server default",
                  )
            }
            className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm bg-white font-mono"
            autoComplete="off"
          />
        </Field>
      </CardContent>
    </Card>
  );
}
