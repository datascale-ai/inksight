"use client";

import { Globe } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Chip, Field } from "@/components/config/shared";
import { LocationPicker } from "@/components/config/location-picker";
import type { LocationValue } from "@/lib/locations";

export function RefreshStrategyEditor({
  tr,
  locale,
  location,
  setLocation,
  language,
  setLanguage,
  contentTone,
  setContentTone,
  characterTones,
  setCharacterTones,
  customPersonaTone,
  setCustomPersonaTone,
  handleAddCustomPersona,
  strategy,
  setStrategy,
  refreshMin,
  setRefreshMin,
  languageOptions,
  toneOptions,
  personaPresets,
  strategies,
}: {
  tr: (zh: string, en: string) => string;
  locale: "zh" | "en";
  location: LocationValue;
  setLocation: (value: LocationValue) => void;
  language: string;
  setLanguage: (value: string) => void;
  contentTone: string;
  setContentTone: (value: string) => void;
  characterTones: string[];
  setCharacterTones: React.Dispatch<React.SetStateAction<string[]>>;
  customPersonaTone: string;
  setCustomPersonaTone: (value: string) => void;
  handleAddCustomPersona: () => void;
  strategy: string;
  setStrategy: (value: string) => void;
  refreshMin: number;
  setRefreshMin: (value: number) => void;
  languageOptions: readonly { value: string; label: string }[];
  toneOptions: readonly { value: string; label: string }[];
  personaPresets: readonly string[];
  strategies: Record<string, string>;
}) {
  const customPresets = characterTones.filter(
    (value) => !personaPresets.includes(value),
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Globe size={18} /> {tr("个性化设置", "Preferences")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <Field label={tr("城市（全局默认）", "City (global default)")}>
          <LocationPicker
            value={location}
            onChange={setLocation}
            locale={locale}
            placeholder={tr("如：深圳", "e.g. Shenzhen")}
            helperText={tr("搜索后请选择具体地点，例如：上海 · 中国、巴黎 · 法国、Singapore · Singapore。", "Search and choose a specific place, for example Shanghai · China, Paris · France, or Singapore · Singapore.")}
            className="w-full rounded-sm border border-ink/20 px-3 py-2 text-sm"
          />
        </Field>
        <Field label={tr("语言", "Language")}>
          <div className="flex flex-wrap gap-2">
            {languageOptions.map((opt) => (
              <Chip
                key={opt.value}
                selected={language === opt.value}
                onClick={() => setLanguage(opt.value)}
              >
                {opt.label}
              </Chip>
            ))}
          </div>
        </Field>
        <Field label={tr("内容语气", "Tone")}>
          <div className="flex flex-wrap gap-2">
            {toneOptions.map((opt) => (
              <Chip
                key={opt.value}
                selected={contentTone === opt.value}
                onClick={() => setContentTone(opt.value)}
              >
                {opt.label}
              </Chip>
            ))}
          </div>
        </Field>
        <Field label={tr("人设风格", "Persona Style")}>
          <div className="flex flex-wrap gap-2">
            {personaPresets.map((value) => (
              <Chip
                key={value}
                selected={characterTones.includes(value)}
                onClick={() =>
                  setCharacterTones((prev) =>
                    prev.includes(value)
                      ? prev.filter((item) => item !== value)
                      : [...prev, value],
                  )
                }
              >
                {value}
              </Chip>
            ))}
          </div>
          <div className="mt-2 flex gap-2">
            <input
              value={customPersonaTone}
              onChange={(e) => setCustomPersonaTone(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleAddCustomPersona();
                }
              }}
              placeholder={tr("自定义人设风格", "Custom persona style")}
              className="flex-1 rounded-sm border border-ink/20 px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={handleAddCustomPersona}
              className="rounded-sm border border-ink/20 px-3 py-2 text-sm"
            >
              {tr("添加", "Add")}
            </button>
          </div>
          {customPresets.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {customPresets.map((value) => (
                <Chip
                  key={value}
                  selected
                  onClick={() =>
                    setCharacterTones((prev) => prev.filter((item) => item !== value))
                  }
                >
                  {value}
                </Chip>
              ))}
            </div>
          )}
        </Field>
        <Field label={tr("刷新策略", "Refresh Strategy")}>
          <div className="grid grid-cols-2 gap-2 mb-3">
            {Object.entries(strategies).map(([key, desc]) => (
              <button
                key={key}
                onClick={() => setStrategy(key)}
                className={`group p-3 rounded-sm border text-left transition-colors ${
                  strategy === key
                    ? "border-ink bg-ink text-white"
                    : "border-ink/10 hover:bg-ink hover:text-white"
                }`}
              >
                <div className="text-sm font-medium">{key}</div>
                <div
                  className={`text-xs mt-1 ${
                    strategy === key
                      ? "text-white/70"
                      : "text-ink-light group-hover:text-white/80"
                  }`}
                >
                  {desc}
                </div>
              </button>
            ))}
          </div>
          <label className="block text-sm font-medium mb-2">
            {tr("刷新间隔 (分钟)", "Refresh interval (minutes)")}
          </label>
          <input
            type="number"
            min={10}
            max={1440}
            value={refreshMin}
            onChange={(e) => setRefreshMin(Number(e.target.value))}
            className="w-32 rounded-sm border border-ink/20 px-3 py-2 text-sm"
          />
          <p className="mt-2 text-xs text-ink-light">
            {tr("可设置范围：10-1440 分钟", "Allowed range: 10-1440 minutes")}
          </p>
        </Field>
      </CardContent>
    </Card>
  );
}
