"use client";

import { useCallback, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Plus, Minus, RotateCcw } from "lucide-react";

export interface TimetableData {
  style: "daily" | "weekly";
  periods: string[];
  courses: Record<string, string>;
}

interface TimetableEditorProps {
  data: TimetableData;
  onChange: (data: TimetableData) => void;
  tr: (zh: string, en: string) => string;
}

const WEEKDAYS_ZH = ["一", "二", "三", "四", "五"];
const WEEKDAYS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri"];

const TEMPLATE_UNIVERSITY_ZH: TimetableData = {
  style: "weekly",
  periods: ["08:00-09:30", "10:00-11:30", "14:00-15:30", "16:00-17:30"],
  courses: {
    "0-0": "高等数学/A201", "0-2": "线性代数/A201",
    "1-1": "大学英语/B305", "1-3": "体育/操场",
    "2-0": "数据结构/C102", "2-2": "计算机网络/C102",
    "3-1": "概率论/A201", "3-3": "毛概/D405",
    "4-0": "操作系统/C102",
  },
};

const TEMPLATE_UNIVERSITY_EN: TimetableData = {
  style: "weekly",
  periods: ["08:00-09:30", "10:00-11:30", "14:00-15:30", "16:00-17:30"],
  courses: {
    "0-0": "Calculus/A201", "0-2": "Linear Algebra/A201",
    "1-1": "English/B305", "1-3": "PE/Gym",
    "2-0": "Data Struct/C102", "2-2": "Networks/C102",
    "3-1": "Probability/A201", "3-3": "Politics/D405",
    "4-0": "OS/C102",
  },
};

const TEMPLATE_K12_ZH: TimetableData = {
  style: "weekly",
  periods: ["第1节", "第2节", "第3节", "第4节", "第5节", "第6节", "第7节", "第8节"],
  courses: {
    "0-0": "语文", "0-1": "数学", "0-2": "英语", "0-3": "物理",
    "0-4": "化学", "0-5": "生物", "0-6": "历史", "0-7": "数学",
    "1-0": "数学", "1-1": "语文", "1-2": "物理", "1-3": "化学",
    "1-4": "英语", "1-5": "政治", "1-6": "地理", "1-7": "语文",
    "2-0": "英语", "2-1": "物理", "2-2": "数学", "2-3": "语文",
    "2-4": "生物", "2-5": "化学", "2-6": "政治", "2-7": "物理",
    "3-0": "物理", "3-1": "化学", "3-2": "语文", "3-3": "数学",
    "3-4": "历史", "3-5": "地理", "3-6": "英语", "3-7": "化学",
    "4-0": "化学", "4-1": "英语", "4-2": "生物", "4-3": "历史",
    "4-4": "语文", "4-5": "数学", "4-6": "地理", "4-7": "英语",
  },
};

const TEMPLATE_K12_EN: TimetableData = {
  style: "weekly",
  periods: ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"],
  courses: {
    "0-0": "Chinese", "0-1": "Math", "0-2": "English", "0-3": "Physics",
    "0-4": "Chemistry", "0-5": "Biology", "0-6": "History", "0-7": "Math",
    "1-0": "Math", "1-1": "Chinese", "1-2": "Physics", "1-3": "Chemistry",
    "1-4": "English", "1-5": "Politics", "1-6": "Geography", "1-7": "Chinese",
    "2-0": "English", "2-1": "Physics", "2-2": "Math", "2-3": "Chinese",
    "2-4": "Biology", "2-5": "Chemistry", "2-6": "Politics", "2-7": "Physics",
    "3-0": "Physics", "3-1": "Chemistry", "3-2": "Chinese", "3-3": "Math",
    "3-4": "History", "3-5": "Geography", "3-6": "English", "3-7": "Chemistry",
    "4-0": "Chemistry", "4-1": "English", "4-2": "Biology", "4-3": "History",
    "4-4": "Chinese", "4-5": "Math", "4-6": "Geography", "4-7": "English",
  },
};

type TemplateType = "university" | "k12";

function detectTemplate(data: TimetableData): TemplateType {
  return data.periods.some((p) => p.startsWith("第")) ? "k12" : "university";
}

export function TimetableEditor({ data, onChange, tr }: TimetableEditorProps) {
  const [editingCell, setEditingCell] = useState<string | null>(null);
  const [editingPeriod, setEditingPeriod] = useState<number | null>(null);
  const [draft, setDraft] = useState("");

  const isEn = tr("zh", "en") === "en";
  const weekdays = isEn ? WEEKDAYS_EN : WEEKDAYS_ZH;
  const templateType = useMemo(() => detectTemplate(data), [data]);

  const getTemplate = useCallback((t: TemplateType) => {
    if (t === "k12") return isEn ? { ...TEMPLATE_K12_EN } : { ...TEMPLATE_K12_ZH };
    return isEn ? { ...TEMPLATE_UNIVERSITY_EN } : { ...TEMPLATE_UNIVERSITY_ZH };
  }, [isEn]);

  const switchTemplate = useCallback((t: TemplateType) => {
    onChange(getTemplate(t));
  }, [onChange, getTemplate]);

  const setCourse = useCallback((key: string, value: string) => {
    const next = { ...data.courses };
    if (value.trim()) {
      next[key] = value.trim();
    } else {
      delete next[key];
    }
    onChange({ ...data, courses: next });
  }, [data, onChange]);

  const setPeriodLabel = useCallback((idx: number, value: string) => {
    const next = [...data.periods];
    next[idx] = value;
    onChange({ ...data, periods: next });
  }, [data, onChange]);

  const addPeriod = useCallback(() => {
    const n = data.periods.length + 1;
    const label = templateType === "k12" ? (isEn ? `P${n}` : `第${n}节`) : `${8 + (n - 1) * 2}:00`;
    onChange({ ...data, periods: [...data.periods, label] });
  }, [data, onChange, templateType, isEn]);

  const removePeriod = useCallback(() => {
    if (data.periods.length <= 1) return;
    const pi = data.periods.length - 1;
    const next = { ...data.courses };
    for (let di = 0; di < 5; di++) {
      delete next[`${di}-${pi}`];
    }
    onChange({ ...data, periods: data.periods.slice(0, -1), courses: next });
  }, [data, onChange]);

  const resetTemplate = useCallback(() => {
    onChange(getTemplate(templateType));
  }, [templateType, onChange, getTemplate]);

  const commitEdit = useCallback((key: string, value: string) => {
    setCourse(key, value);
    setEditingCell(null);
    setDraft("");
  }, [setCourse]);

  const commitPeriod = useCallback((idx: number, value: string) => {
    if (value.trim()) setPeriodLabel(idx, value.trim());
    setEditingPeriod(null);
    setDraft("");
  }, [setPeriodLabel]);

  const isUniv = templateType === "university";

  return (
    <div className="space-y-3">
      {/* Template toggle */}
      <div className="flex gap-2">
        <button
          type="button"
          className={`flex-1 px-3 py-1.5 text-xs rounded-sm border transition-all ${
            isUniv
              ? "bg-ink text-white border-ink"
              : "bg-transparent text-ink border-ink hover:bg-ink hover:text-white"
          }`}
          onClick={() => switchTemplate("university")}
        >
          {tr("大学课表", "University")}
        </button>
        <button
          type="button"
          className={`flex-1 px-3 py-1.5 text-xs rounded-sm border transition-all ${
            !isUniv
              ? "bg-ink text-white border-ink"
              : "bg-transparent text-ink border-ink hover:bg-ink hover:text-white"
          }`}
          onClick={() => switchTemplate("k12")}
        >
          {tr("中小学课表", "K-12")}
        </button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse border border-ink/20">
          <thead>
            <tr className="bg-paper-dark">
              <th className="border border-ink/20 px-1 py-1 text-center w-16">
                {tr("时间", "Time")}
              </th>
              {weekdays.map((wd, i) => (
                <th key={i} className="border border-ink/20 px-1 py-1 text-center">
                  {wd}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.periods.map((period, pi) => (
              <tr key={pi}>
                <td
                  className="border border-ink/20 px-1 py-1 text-center cursor-pointer hover:bg-paper-dark text-ink/70 font-mono text-[10px]"
                  onClick={() => {
                    setEditingPeriod(pi);
                    setDraft(period);
                    setEditingCell(null);
                  }}
                >
                  {editingPeriod === pi ? (
                    <input
                      autoFocus
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onBlur={() => commitPeriod(pi, draft)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitPeriod(pi, draft);
                        if (e.key === "Escape") { setEditingPeriod(null); setDraft(""); }
                      }}
                      className="w-full text-center text-[10px] bg-white border-0 outline-none px-0 py-0"
                    />
                  ) : (
                    period
                  )}
                </td>
                {weekdays.map((_, di) => {
                  const key = `${di}-${pi}`;
                  const val = data.courses[key] || "";
                  const isEditing = editingCell === key;
                  return (
                    <td
                      key={key}
                      className={`border border-ink/20 px-1 py-1 text-center cursor-pointer hover:bg-blue-50 min-w-[52px] ${
                        val ? "" : "text-ink/20"
                      }`}
                      onClick={() => {
                        if (!isEditing) {
                          setEditingCell(key);
                          setDraft(val);
                          setEditingPeriod(null);
                        }
                      }}
                    >
                      {isEditing ? (
                        <input
                          autoFocus
                          value={draft}
                          onChange={(e) => setDraft(e.target.value)}
                          onBlur={() => commitEdit(key, draft)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") commitEdit(key, draft);
                            if (e.key === "Escape") { setEditingCell(null); setDraft(""); }
                          }}
                          placeholder={isUniv ? tr("课名/教室", "Name/Room") : tr("课名", "Name")}
                          className="w-full text-center text-xs bg-white border-0 outline-none px-0 py-0"
                        />
                      ) : (
                        val || "—"
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={addPeriod} className="h-7 px-2 text-xs">
          <Plus className="w-3 h-3 mr-1" />
          {tr("添加节次", "Add Period")}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={removePeriod}
          disabled={data.periods.length <= 1}
          className="h-7 px-2 text-xs"
        >
          <Minus className="w-3 h-3 mr-1" />
          {tr("删除末行", "Remove Last")}
        </Button>
        <Button variant="ghost" size="sm" onClick={resetTemplate} className="h-7 px-2 text-xs ml-auto">
          <RotateCcw className="w-3 h-3 mr-1" />
          {tr("使用模板", "Use Template")}
        </Button>
      </div>
    </div>
  );
}
