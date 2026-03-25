"use client";

import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import { Plus, X } from "lucide-react";

interface CalendarRemindersProps {
  reminders: Record<string, string>;
  onChange: (reminders: Record<string, string>) => void;
  tr: (zh: string, en: string) => string;
}

export function CalendarReminders({ reminders, onChange, tr }: CalendarRemindersProps) {
  const [draftDate, setDraftDate] = useState("");
  const [draftText, setDraftText] = useState("");

  const handleAdd = useCallback(() => {
    if (!draftDate || !draftText.trim()) return;
    const d = new Date(draftDate);
    if (isNaN(d.getTime())) return;
    const key = `${d.getMonth() + 1}-${d.getDate()}`;
    onChange({ ...reminders, [key]: draftText.trim() });
    setDraftDate("");
    setDraftText("");
  }, [draftDate, draftText, onChange, reminders]);

  const handleDelete = useCallback(
    (key: string) => {
      const next = { ...reminders };
      delete next[key];
      onChange(next);
    },
    [onChange, reminders],
  );

  const sorted = Object.entries(reminders).sort(([a], [b]) => {
    const [am, ad] = a.split("-").map(Number);
    const [bm, bd] = b.split("-").map(Number);
    return am !== bm ? am - bm : ad - bd;
  });

  const formatKey = (key: string) => {
    const [m, d] = key.split("-");
    return `${m}${tr("月", "/")}${d}${tr("日", "")}`;
  };

  return (
    <div className="border border-ink/10 rounded-md p-3 space-y-2">
      <div className="text-xs font-medium text-ink/70">{tr("日历提醒", "Calendar Reminders")}</div>
      {sorted.length > 0 && (
        <div className="space-y-1">
          {sorted.map(([key, text]) => (
            <div key={key} className="flex items-center gap-2 text-xs">
              <span className="text-ink/60 min-w-[48px]">{formatKey(key)}</span>
              <span className="flex-1 truncate">{text}</span>
              <button
                type="button"
                onClick={() => handleDelete(key)}
                className="text-ink/40 hover:text-ink p-0.5"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2">
        <input
          type="date"
          value={draftDate}
          onChange={(e) => setDraftDate(e.target.value)}
          className="border border-ink/20 rounded px-2 py-1 text-xs bg-white"
        />
        <input
          type="text"
          value={draftText}
          onChange={(e) => setDraftText(e.target.value)}
          placeholder={tr("提醒内容", "Reminder")}
          maxLength={20}
          className="border border-ink/20 rounded px-2 py-1 text-xs flex-1 bg-white"
          onKeyDown={(e) => {
            if (e.key === "Enter") handleAdd();
          }}
        />
        <Button
          variant="outline"
          size="sm"
          onClick={handleAdd}
          disabled={!draftDate || !draftText.trim()}
          className="h-7 px-2 text-xs"
        >
          <Plus className="w-3 h-3 mr-1" />
          {tr("添加", "Add")}
        </Button>
      </div>
    </div>
  );
}
