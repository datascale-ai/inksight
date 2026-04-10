"use client";

import { Globe, Plus, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Chip, Field } from "@/components/config/shared";
import { LocationPicker } from "@/components/config/location-picker";
import type { LocationValue } from "@/lib/locations";

/** 时段规则数据结构，与后端 time_slot_rules 字段对齐 */
export interface TimeSlotRule {
  startHour: number;
  endHour: number;
  modes: string[];
}

export function RefreshStrategyEditor({
  tr,
  locale,
  location,
  setLocation,
  modeLanguage,
  setModeLanguage,
  modeLanguageOptions,
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
  toneOptions,
  personaPresets,
  strategies,
  timeSlotRules,
  setTimeSlotRules,
  availableModes,
  modeMeta,
}: {
  tr: (zh: string, en: string) => string;
  locale: "zh" | "en";
  location: LocationValue;
  setLocation: (value: LocationValue) => void;
  modeLanguage: string;
  setModeLanguage: (value: string) => void;
  modeLanguageOptions: readonly { value: string; label: string; labelEn: string }[];
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
  toneOptions: readonly { value: string; label: string }[];
  personaPresets: readonly string[];
  strategies: Record<string, string>;
  timeSlotRules: TimeSlotRule[];
  setTimeSlotRules: (rules: TimeSlotRule[]) => void;
  availableModes: string[];
  modeMeta: Record<string, { name: string; tip: string }>;
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
            {modeLanguageOptions.map((opt) => (
              <Chip
                key={opt.value}
                selected={modeLanguage === opt.value}
                onClick={() => setModeLanguage(opt.value)}
              >
                {locale === "en" ? opt.labelEn : opt.label}
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

        {/* 时段规则编辑区：仅 time_slot 策略时显示 */}
        {strategy === "time_slot" && (
          <TimeSlotRulesEditor
            tr={tr}
            rules={timeSlotRules}
            onChange={setTimeSlotRules}
            availableModes={availableModes}
            modeMeta={modeMeta}
          />
        )}
      </CardContent>
    </Card>
  );
}

/** 时段规则编辑器子组件 */
function TimeSlotRulesEditor({
  tr,
  rules,
  onChange,
  availableModes,
  modeMeta,
}: {
  tr: (zh: string, en: string) => string;
  rules: TimeSlotRule[];
  onChange: (rules: TimeSlotRule[]) => void;
  availableModes: string[];
  modeMeta: Record<string, { name: string; tip: string }>;
}) {
  const addRule = () => {
    if (rules.length >= 12) return;
    onChange([...rules, { startHour: 9, endHour: 12, modes: [] }]);
  };

  const updateRule = (index: number, patch: Partial<TimeSlotRule>) => {
    onChange(rules.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  };

  const removeRule = (index: number) => {
    onChange(rules.filter((_, i) => i !== index));
  };

  return (
    <div className="rounded-sm border border-ink/15 bg-paper p-4 space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-ink">{tr("时段规则", "Time Slot Rules")}</label>
        <span className="text-xs text-ink-light">{rules.length}/12</span>
      </div>

      {rules.length === 0 && (
        <p className="text-xs text-ink-light">{tr("暂无时段规则，点击下方按钮添加", "No rules yet. Click below to add one.")}</p>
      )}

      <div className="space-y-3 max-h-72 overflow-y-auto">
        {rules.map((rule, index) => (
          <TimeSlotRuleRow
            key={index}
            rule={rule}
            onChange={(patch) => updateRule(index, patch)}
            onRemove={() => removeRule(index)}
            availableModes={availableModes}
            modeMeta={modeMeta}
            tr={tr}
          />
        ))}
      </div>

      <button
        type="button"
        onClick={addRule}
        disabled={rules.length >= 12}
        className="flex items-center gap-2 rounded-sm border border-ink/20 px-3 py-2 text-sm text-ink hover:bg-ink hover:text-white transition-colors disabled:opacity-40 disabled:hover:bg-white disabled:hover:text-ink"
      >
        <Plus size={14} />
        {tr("添加时段", "Add Time Slot")}
      </button>

      <p className="text-xs text-ink-light">{tr("为不同时间段配置不同的内容模式，未覆盖的时段使用随机选择", "Configure different modes for different time periods. Uncovered hours use random selection.")}</p>
    </div>
  );
}

/** 单条时段规则行 */
function TimeSlotRuleRow({
  rule,
  onChange,
  onRemove,
  availableModes,
  modeMeta,
  tr,
}: {
  rule: TimeSlotRule;
  onChange: (patch: Partial<TimeSlotRule>) => void;
  onRemove: () => void;
  availableModes: string[];
  modeMeta: Record<string, { name: string; tip: string }>;
  tr: (zh: string, en: string) => string;
}) {
  const addMode = (mode: string) => {
    if (!rule.modes.includes(mode)) {
      onChange({ modes: [...rule.modes, mode] });
    }
  };

  const removeMode = (mode: string) => {
    onChange({ modes: rule.modes.filter((m) => m !== mode) });
  };

  const unselectedModes = availableModes.filter((m) => !rule.modes.includes(m));

  return (
    <div className="rounded-sm border border-ink/10 bg-white p-3 space-y-2">
      {/* 时间段输入 */}
      <div className="flex items-center gap-2 flex-wrap">
        <input
          type="number"
          min={0}
          max={23}
          value={rule.startHour}
          onChange={(e) => onChange({ startHour: Number(e.target.value) })}
          className="w-16 rounded-sm border border-ink/20 px-2 py-1.5 text-sm text-center"
        />
        <span className="text-sm text-ink-light">—</span>
        <input
          type="number"
          min={0}
          max={24}
          value={rule.endHour}
          onChange={(e) => onChange({ endHour: Number(e.target.value) })}
          className="w-16 rounded-sm border border-ink/20 px-2 py-1.5 text-sm text-center"
        />
        <span className="text-sm text-ink-light">{tr("时", "h")}</span>
        <button
          type="button"
          onClick={onRemove}
          className="ml-auto p-1.5 rounded-sm text-ink hover:bg-red-50 hover:text-red-600 transition-colors"
          title={tr("删除此规则", "Remove rule")}
        >
          <Trash2 size={14} />
        </button>
      </div>

      {/* 模式选择：下拉添加 + Chip 展示已选 */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* 已选模式：Chip 可点击移除 */}
        {rule.modes.map((mode) => (
          <Chip
            key={mode}
            selected
            onClick={() => removeMode(mode)}
          >
            {modeMeta[mode]?.name || mode}
          </Chip>
        ))}

        {/* 下拉选择器添加模式 */}
        {unselectedModes.length > 0 && (
          <select
            value=""
            onChange={(e) => {
              const val = e.target.value;
              if (val) addMode(val);
              e.target.value = ""; // reset
            }}
            className="rounded-sm border border-ink/20 px-2 py-1.5 text-sm bg-white text-ink min-w-[120px] cursor-pointer"
          >
            <option value="">{tr("+ 添加模式", "+ Add mode")}</option>
            {unselectedModes.map((mode) => (
              <option key={mode} value={mode}>
                {modeMeta[mode]?.name || mode}
              </option>
            ))}
          </select>
        )}
      </div>

      {rule.modes.length === 0 && (
        <p className="text-xs text-ink-light">{tr("请至少选择一个模式", "Please select at least one mode")}</p>
      )}
    </div>
  );
}
