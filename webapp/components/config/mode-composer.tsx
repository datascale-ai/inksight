"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor,
  useSensor, useSensors, type DragEndEvent, DragOverlay, type DragStartEvent,
} from "@dnd-kit/core";
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates,
  useSortable, verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Trash2, Copy, Type, AlignCenter, Minus, Layers, Columns, Hash, Image, List, X, Settings2, RefreshCw, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export type ComposerPropMeta = { name: string; label: string; label_zh?: string; type: "string"|"number"|"boolean"|"select"|"textarea"; value_kind?: "field"|"template"|"font"|"font_name"|"plain"; required?: boolean; default?: unknown; options?: string[]; hidden?: boolean };
export type ComposerCatalogItem = { name: string; label: string; label_zh?: string; description?: string; description_zh?: string; props: ComposerPropMeta[] };
export type ComposerCatalog = { version?: number; fonts?: string[]; fragment_stack?: { props?: ComposerPropMeta[] }; fragments?: ComposerCatalogItem[]; presets?: ComposerCatalogItem[] };
export type ComposerFragmentState = { id: string; fragment: string; props: Record<string, unknown> };
export type ComposerLayoutKind = "preset" | "fragments";
export type ComposerState = { layoutKind: ComposerLayoutKind; bodyPreset: string; presetProps: Record<string, unknown>; fragments: ComposerFragmentState[]; fragmentStack: Record<string, unknown>; prompt: string; cacheable: boolean };

export function propDefaultValue(p: ComposerPropMeta) { if (p.default !== undefined) return cj(p.default); if (p.type === "boolean") return false; if (p.type === "number") return 0; if (p.type === "select") return p.options?.[0] ?? ""; return ""; }
export function withPropDefaults(props: Record<string, unknown>, metas: ComposerPropMeta[] | undefined) { const n = cj(props || {}); for (const m of metas || []) { if (!(m.name in n)) { if (m.default !== undefined) { n[m.name] = cj(m.default); } else if (m.required && m.value_kind === "field") { n[m.name] = m.name.replace(/_field$/, ""); } } } return n; }
export function findCatalogItem(items: ComposerCatalogItem[] | undefined, name: string) { return (items || []).find((i) => i.name === name) || null; }
export function randomComposerId() { return `frag_${Math.random().toString(36).slice(2, 10)}`; }
function cj<T>(v: T): T { return JSON.parse(JSON.stringify(v)); }

const FRAG_ICONS: Record<string, typeof Type> = { title_with_rule: AlignCenter, plain_text: Type, separator: Minus, spacer: Layers, two_column: Columns, big_number: Hash, image_block: Image, list_block: List };
function fragIcon(name: string) { const I = FRAG_ICONS[name]; return I ? <I size={16} /> : <Layers size={16} />; }

type ModeComposerProps = { tr: (zh: string, en: string) => string; isEn: boolean; catalog: ComposerCatalog; state: ComposerState; onChange: (u: (p: ComposerState) => ComposerState) => void; syncError: string | null; onPreview: () => void; previewDisabled: boolean; previewImgUrl: string | null; previewLoading: boolean; onRequestPreview: () => void };

function PropInput({ meta: m, value: v, onChange: oc, id: iid, tr, isEn }: { meta: ComposerPropMeta; value: unknown; onChange: (v: unknown) => void; id: string; tr: (z: string, e: string) => string; isEn: boolean }) {
  const label = (!isEn && m.label_zh) ? m.label_zh : m.label;
  if (m.type === "boolean") return <label className="flex items-center gap-2 text-sm text-ink"><input id={iid} type="checkbox" checked={Boolean(v)} onChange={e => oc(e.target.checked)} /><span>{label}</span></label>;
  if (m.type === "select") return <select id={iid} value={String(v ?? "")} onChange={e => oc(e.target.value)} className="w-full rounded border border-ink/20 px-2 py-1 text-sm bg-white"><option value="">{tr("默认","Default")}</option>{(m.options||[]).map(o=><option key={o} value={o}>{o}</option>)}</select>;
  if (m.type === "textarea") return <textarea id={iid} value={String(v ?? "")} onChange={e => oc(e.target.value)} rows={2} className="w-full rounded border border-ink/20 px-2 py-1 text-sm resize-y bg-white" />;
  if (m.type === "number") return <input id={iid} type="number" value={typeof v === "number" ? v : ""} onChange={e => oc(e.target.value === "" ? "" : Number(e.target.value))} className="w-full rounded border border-ink/20 px-2 py-1 text-sm bg-white" />;
  return <input id={iid} type="text" value={String(v ?? "")} onChange={e => oc(e.target.value)} className="w-full rounded border border-ink/20 px-2 py-1 text-sm bg-white" />;
}

function PropPanel({ metas, values, onPropChange, prefix, tr, isEn }: { metas: ComposerPropMeta[]; values: Record<string, unknown>; onPropChange: (n: string, v: unknown) => void; prefix: string; tr: (z: string, e: string) => string; isEn: boolean }) {
  const visible = metas.filter(m => !m.hidden);
  if (!visible.length) return null;
  return <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-2">{visible.map(m => { const id = `${prefix}-${m.name}`; const val = values[m.name] ?? propDefaultValue(m); const label = (!isEn && m.label_zh) ? m.label_zh : m.label; return <div key={m.name} className={m.type === "textarea" ? "sm:col-span-2" : ""}>{m.type === "boolean" ? <PropInput meta={m} value={val} onChange={v => onPropChange(m.name, v)} id={id} tr={tr} isEn={isEn} /> : <><div className="text-[11px] text-ink-light mb-0.5">{label}{m.required ? " *" : ""}</div><PropInput meta={m} value={val} onChange={v => onPropChange(m.name, v)} id={id} tr={tr} isEn={isEn} /></>}</div>; })}</div>;
}

function CanvasCard({ fragment, meta, isEn, tr, isSelected, onSelect, onRemove, onDuplicate }: {
  fragment: ComposerFragmentState; meta: ComposerCatalogItem | null; isEn: boolean;
  tr: (z: string, e: string) => string; isSelected: boolean;
  onSelect: () => void; onRemove: () => void; onDuplicate: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: fragment.id });
  const style = { transform: CSS.Transform.toString(transform), transition, zIndex: isDragging ? 50 : undefined, opacity: isDragging ? 0.8 : 1 };
  const label = meta ? (isEn ? meta.label : (meta.label_zh || meta.label)) : fragment.fragment;
  return (
    <div ref={setNodeRef} style={style} onClick={onSelect}
      className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg border-2 transition-all cursor-pointer select-none ${isDragging ? "shadow-xl border-ink/50 bg-white scale-[1.02]" : isSelected ? "border-ink bg-ink/5 shadow-md" : "border-ink/15 bg-white hover:border-ink/30 hover:shadow"}`}>
      <button type="button" className="cursor-grab active:cursor-grabbing text-ink-light hover:text-ink touch-none shrink-0" {...attributes} {...listeners}>
        <GripVertical size={18} />
      </button>
      <div className="shrink-0 w-8 h-8 rounded-md bg-paper-dark flex items-center justify-center text-ink/60">
        {fragIcon(fragment.fragment)}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-ink truncate">{label}</div>
        {meta?.description_zh || meta?.description ? (
          <div className="text-[11px] text-ink-light truncate">{isEn ? meta.description : (meta.description_zh || meta.description)}</div>
        ) : null}
      </div>
      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
        <button type="button" onClick={e => { e.stopPropagation(); onDuplicate(); }} className="p-1 rounded hover:bg-ink/10 text-ink-light hover:text-ink" title={tr("复制","Duplicate")}><Copy size={14} /></button>
        <button type="button" onClick={e => { e.stopPropagation(); onRemove(); }} className="p-1 rounded hover:bg-red-50 text-ink-light hover:text-red-600" title={tr("删除","Remove")}><Trash2 size={14} /></button>
      </div>
    </div>
  );
}

function DragOverlayCard({ fragment, meta, isEn }: { fragment: ComposerFragmentState; meta: ComposerCatalogItem | null; isEn: boolean }) {
  const label = meta ? (isEn ? meta.label : (meta.label_zh || meta.label)) : fragment.fragment;
  return (
    <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg border-2 border-ink/50 bg-white shadow-2xl scale-[1.05]">
      <GripVertical size={18} className="text-ink-light" />
      <div className="w-8 h-8 rounded-md bg-paper-dark flex items-center justify-center text-ink/60">{fragIcon(fragment.fragment)}</div>
      <div className="text-sm font-medium text-ink">{label}</div>
    </div>
  );
}

function PaletteItem({ item, isEn, onAdd }: { item: ComposerCatalogItem; isEn: boolean; onAdd: () => void }) {
  return (
    <button type="button" onClick={onAdd}
      className="flex items-center gap-2 px-2.5 py-2 rounded-lg border border-ink/10 bg-white hover:border-ink/30 hover:shadow transition-all text-left w-full">
      <div className="shrink-0 w-7 h-7 rounded-md bg-paper-dark flex items-center justify-center text-ink/50">
        {fragIcon(item.name)}
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-xs font-medium text-ink truncate">{isEn ? item.label : (item.label_zh || item.label)}</div>
      </div>
    </button>
  );
}

export function ModeComposer({ tr, isEn, catalog, state, onChange, syncError, onPreview, previewDisabled, previewImgUrl, previewLoading, onRequestPreview }: ModeComposerProps) {
  const fragOpts = catalog.fragments || [];
  const presetOpts = catalog.presets || [];
  const stackProps = catalog.fragment_stack?.props || [];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [showStackSettings, setShowStackSettings] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const fragIds = useMemo(() => state.fragments.map(f => f.id), [state.fragments]);
  const selectedFrag = state.fragments.find(f => f.id === selectedId) || null;
  const selectedMeta = selectedFrag ? findCatalogItem(fragOpts, selectedFrag.fragment) : null;
  const draggingFrag = state.fragments.find(f => f.id === draggingId) || null;
  const draggingMeta = draggingFrag ? findCatalogItem(fragOpts, draggingFrag.fragment) : null;

  const handleDragStart = useCallback((e: DragStartEvent) => { setDraggingId(String(e.active.id)); }, []);
  const handleDragEnd = useCallback((e: DragEndEvent) => {
    setDraggingId(null);
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    onChange(prev => {
      const oi = prev.fragments.findIndex(f => f.id === active.id);
      const ni = prev.fragments.findIndex(f => f.id === over.id);
      if (oi < 0 || ni < 0) return prev;
      return { ...prev, fragments: arrayMove(prev.fragments, oi, ni) };
    });
  }, [onChange]);

  const addFrag = useCallback((name: string) => {
    const m = findCatalogItem(fragOpts, name);
    const newId = randomComposerId();
    onChange(prev => ({ ...prev, layoutKind: "fragments" as const, fragments: [...prev.fragments, { id: newId, fragment: name, props: withPropDefaults({}, m?.props) }] }));
    setSelectedId(newId);
  }, [fragOpts, onChange]);

  const dupFrag = useCallback((id: string) => {
    onChange(prev => {
      const idx = prev.fragments.findIndex(f => f.id === id);
      if (idx < 0) return prev;
      const src = prev.fragments[idx];
      const copy = { id: randomComposerId(), fragment: src.fragment, props: cj(src.props) };
      const next = [...prev.fragments]; next.splice(idx + 1, 0, copy);
      return { ...prev, fragments: next };
    });
  }, [onChange]);

  const rmFrag = useCallback((id: string) => {
    if (selectedId === id) setSelectedId(null);
    onChange(prev => ({ ...prev, fragments: prev.fragments.filter(f => f.id !== id) }));
  }, [onChange, selectedId]);

  const changeType = useCallback((id: string, name: string) => {
    const m = findCatalogItem(fragOpts, name);
    onChange(prev => ({ ...prev, fragments: prev.fragments.map(f => f.id === id ? { ...f, fragment: name, props: withPropDefaults({}, m?.props) } : f) }));
  }, [fragOpts, onChange]);

  const changeProp = useCallback((id: string, pn: string, v: unknown) => {
    onChange(prev => ({ ...prev, fragments: prev.fragments.map(f => f.id === id ? { ...f, props: { ...f.props, [pn]: v } } : f) }));
  }, [onChange]);

  const activePresetMeta = findCatalogItem(presetOpts, state.bodyPreset);

  return (
    <div className="space-y-3">
      <div className="flex gap-3 items-start">
        <div className="flex-1">
          <div className="text-[11px] text-ink-light mb-1">{tr("内容提示词","Content prompt")}</div>
          <textarea value={state.prompt} onChange={e => onChange(p => ({ ...p, prompt: e.target.value }))} rows={2}
            className="w-full rounded border border-ink/20 px-2 py-1.5 text-sm resize-y bg-white"
            placeholder={tr("例如：每天生成一句简洁有力量的话。","e.g. generate one concise uplifting line each day.")} />
        </div>
        <div className="flex flex-col gap-1.5 pt-4 shrink-0">
          <label className="flex items-center gap-1.5 text-xs text-ink">
            <input type="checkbox" checked={state.cacheable} onChange={e => onChange(p => ({ ...p, cacheable: e.target.checked }))} />
            {tr("缓存","Cache")}
          </label>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="text-xs text-ink-light">{tr("布局","Layout")}:</div>
        <button type="button" onClick={() => onChange(p => ({ ...p, layoutKind: "preset" }))}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${state.layoutKind === "preset" ? "bg-ink text-white" : "bg-paper-dark text-ink hover:bg-ink/10"}`}>
          {tr("预设模板","Preset")}
        </button>
        <button type="button" onClick={() => onChange(p => ({ ...p, layoutKind: "fragments", fragments: p.fragments.length > 0 ? p.fragments : (() => { const f = catalog.fragments?.[0]; return f ? [{ id: randomComposerId(), fragment: f.name, props: withPropDefaults({}, f.props) }] : []; })() }))}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${state.layoutKind === "fragments" ? "bg-ink text-white" : "bg-paper-dark text-ink hover:bg-ink/10"}`}>
          {tr("自由拼装","Fragments")}
        </button>
      </div>

      {state.layoutKind === "preset" ? (
        <div className="rounded-lg border border-ink/15 bg-white shadow-sm overflow-hidden">
          <div className="px-3 py-2 bg-paper-dark/60 border-b border-ink/10">
            <select value={state.bodyPreset} onChange={e => { const n = e.target.value; const m = findCatalogItem(presetOpts, n); onChange(p => ({ ...p, bodyPreset: n, presetProps: withPropDefaults({}, m?.props) })); }}
              className="w-full rounded border border-ink/20 px-2 py-1.5 text-sm bg-white font-medium">
              {presetOpts.map(p => <option key={p.name} value={p.name}>{isEn ? p.label : (p.label_zh || p.label)}</option>)}
            </select>
          </div>
          {activePresetMeta ? (
            <div className="px-3 py-3 space-y-2">
              {(activePresetMeta.description || activePresetMeta.description_zh) ? (
                <div className="text-[11px] text-ink-light">{isEn ? activePresetMeta.description : (activePresetMeta.description_zh || activePresetMeta.description)}</div>
              ) : null}
              <PropPanel metas={activePresetMeta.props} values={state.presetProps}
                onPropChange={(n, v) => onChange(p => ({ ...p, presetProps: { ...p.presetProps, [n]: v } }))}
                prefix="preset" tr={tr} isEn={isEn} />
            </div>
          ) : null}
        </div>
      ) : (
        <div className="flex gap-3" style={{ minHeight: 300 }}>
          <div className="w-36 shrink-0 space-y-1.5 overflow-y-auto max-h-[50vh] pr-1">
            <div className="text-[11px] text-ink-light font-medium mb-1 sticky top-0 bg-white/90 backdrop-blur-sm py-1 z-10">
              {tr("组件","Components")}
            </div>
            {fragOpts.map(item => (
              <PaletteItem key={item.name} item={item} isEn={isEn} onAdd={() => addFrag(item.name)} />
            ))}
          </div>

          <div className="flex-1 min-w-0">
            {stackProps.length > 0 ? (
              <div className="mb-2">
                <button type="button" onClick={() => setShowStackSettings(v => !v)}
                  className="flex items-center gap-1 text-[11px] text-ink-light hover:text-ink transition-colors">
                  <Settings2 size={12} />
                  {tr("栈布局设置","Stack settings")}
                </button>
                {showStackSettings ? (
                  <div className="mt-1.5 rounded border border-ink/10 bg-paper/40 px-3 py-2">
                    <PropPanel metas={stackProps} values={state.fragmentStack}
                      onPropChange={(n, v) => onChange(p => ({ ...p, fragmentStack: { ...p.fragmentStack, [n]: v } }))}
                      prefix="stack" tr={tr} isEn={isEn} />
                  </div>
                ) : null}
              </div>
            ) : null}

            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
              <SortableContext items={fragIds} strategy={verticalListSortingStrategy}>
                <div className="space-y-2">
                  {state.fragments.map(f => {
                    const m = findCatalogItem(fragOpts, f.fragment);
                    return <CanvasCard key={f.id} fragment={f} meta={m} isEn={isEn} tr={tr}
                      isSelected={selectedId === f.id} onSelect={() => setSelectedId(selectedId === f.id ? null : f.id)}
                      onRemove={() => rmFrag(f.id)} onDuplicate={() => dupFrag(f.id)} />;
                  })}
                </div>
              </SortableContext>
              <DragOverlay dropAnimation={{ duration: 200, easing: "ease" }}>
                {draggingFrag ? <DragOverlayCard fragment={draggingFrag} meta={draggingMeta} isEn={isEn} /> : null}
              </DragOverlay>
            </DndContext>

            {state.fragments.length === 0 ? (
              <div className="flex items-center justify-center h-24 rounded-lg border-2 border-dashed border-ink/15 text-sm text-ink-light">
                {tr("从左侧点击组件添加","Click components on the left to add")}
              </div>
            ) : null}
          </div>

          {selectedFrag && selectedMeta ? (
            <div className="w-56 shrink-0 overflow-y-auto max-h-[50vh]">
              <div className="rounded-lg border border-ink/15 bg-white shadow-sm overflow-hidden">
                <div className="flex items-center justify-between px-3 py-2 bg-paper-dark/60 border-b border-ink/10">
                  <div className="text-xs font-medium text-ink truncate">{isEn ? selectedMeta.label : (selectedMeta.label_zh || selectedMeta.label)}</div>
                  <button type="button" onClick={() => setSelectedId(null)} className="p-0.5 text-ink-light hover:text-ink"><X size={14} /></button>
                </div>
                <div className="px-3 py-2 space-y-2">
                  <div className="text-[11px] text-ink-light mb-1">{tr("类型","Type")}</div>
                  <select value={selectedFrag.fragment} onChange={e => changeType(selectedFrag.id, e.target.value)}
                    className="w-full rounded border border-ink/20 px-2 py-1 text-sm bg-white">
                    {fragOpts.map(i => <option key={i.name} value={i.name}>{isEn ? i.label : (i.label_zh || i.label)}</option>)}
                  </select>
                  <PropPanel metas={selectedMeta.props} values={withPropDefaults(selectedFrag.props, selectedMeta.props)}
                    onPropChange={(n, v) => changeProp(selectedFrag.id, n, v)}
                    prefix={selectedFrag.id} tr={tr} isEn={isEn} />
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {syncError ? <div className="text-xs text-red-600">{syncError}</div> : null}

      {/* Live preview */}
      <div className="rounded-lg border border-ink/15 bg-paper-dark/30 overflow-hidden">
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-ink/10">
          <div className="text-xs font-medium text-ink">{tr("实时预览","Live Preview")}</div>
          <button type="button" onClick={onRequestPreview} disabled={previewLoading}
            className="flex items-center gap-1 text-xs text-ink-light hover:text-ink disabled:opacity-40 transition-colors">
            {previewLoading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            {tr("预览布局","Preview Layout")}
          </button>
        </div>
        <div className="flex items-center justify-center p-3 min-h-[120px] bg-white">
          {previewLoading ? (
            <div className="flex items-center gap-2 text-sm text-ink-light">
              <Loader2 size={16} className="animate-spin" />
              {tr("渲染中...","Rendering...")}
            </div>
          ) : previewImgUrl ? (
            <img src={previewImgUrl} alt="preview" className="max-w-full max-h-[240px] object-contain border border-ink/10 rounded" />
          ) : (
            <div className="text-sm text-ink-light">{tr("点击「预览布局」查看框架效果","Click 'Preview Layout' to see the layout")}</div>
          )}
        </div>
      </div>

      <div className="flex gap-2 pt-1">
        <Button type="button" size="sm" onClick={onPreview} disabled={previewDisabled}>
          {tr("生成内容并预览","Generate & Preview")}
        </Button>
      </div>
    </div>
  );
}
