import { apiRequest, apiFetch } from '@/lib/api-client';

/** RN Hermes 上 blob/FileReader 不可靠，用纯 JS 将 PNG 字节转为 data URI。 */
function uint8ArrayToBase64(bytes: Uint8Array): string {
  const table = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  let out = '';
  let i = 0;
  const len = bytes.length;
  while (i < len) {
    const b1 = bytes[i++]!;
    const b2 = i < len ? bytes[i++] : undefined;
    const b3 = i < len ? bytes[i++] : undefined;
    const enc1 = b1 >> 2;
    const enc2 = ((b1 & 3) << 4) | (b2 === undefined ? 0 : b2 >> 4);
    out += table[enc1]! + table[enc2]!;
    if (b2 === undefined) {
      out += '==';
    } else if (b3 === undefined) {
      out += table[((b2 & 15) << 2)]! + '=';
    } else {
      out += table[((b2 & 15) << 2) | (b3 >> 6)]! + table[b3 & 63]!;
    }
  }
  return out;
}

export type ModeCatalogItem = {
  mode_id: string;
  display_name: string;
  icon: string;
  cacheable: boolean;
  description: string;
  source: string;
  settings_schema?: Array<Record<string, unknown>>;
};

export type CustomModeDefinition = {
  mode_id: string;
  display_name: string;
  icon: string;
  cacheable: boolean;
  description: string;
  content: {
    type: 'static';
    static_data: {
      text: string;
    };
  };
  layout: {
    status_bar: {
      line_width: number;
    };
    body: Array<{
      type: 'centered_text';
      field: string;
      font: string;
      font_size: number;
      vertical_center: boolean;
    }>;
    footer: {
      label: string;
    };
  };
};

export type CustomModePreview = {
  ok: boolean;
  mode_id: string;
  preview_text: string;
  content: Record<string, unknown>;
};

export async function previewCustomMode(token: string, modeDef: CustomModeDefinition) {
  return apiRequest<CustomModePreview>('/modes/custom/preview', {
    method: 'POST',
    token,
    body: {
      mode_def: modeDef,
      responseType: 'json',
    },
  });
}

/**
 * 请求 PNG 图片预览，返回 data URI（可用于 <Image source={{ uri: ... }} />）。
 * 默认返回 400x300 的预览图。
 */
export async function previewCustomModeImage(
  token: string,
  modeDef: CustomModeDefinition,
  { width = 400, height = 300 }: { width?: number; height?: number } = {},
): Promise<string> {
  const response = await apiFetch('/modes/custom/preview', {
    method: 'POST',
    token,
    body: {
      mode_def: modeDef,
      responseType: 'image',
      w: width,
      h: height,
    },
  });

  if (!response.ok) {
    let msg = `${response.status} ${response.statusText}`;
    const ct = response.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      try {
        const json = (await response.json()) as { error?: string };
        msg = json.error || msg;
      } catch { /* ignore */ }
    }
    throw new Error(msg);
  }

  const buffer = await response.arrayBuffer();
  const ct = (response.headers.get('content-type') || 'image/png').split(';')[0]!.trim();
  const mime = ct.startsWith('image/') ? ct : 'image/png';
  const b64 = uint8ArrayToBase64(new Uint8Array(buffer));
  return `data:${mime};base64,${b64}`;
}

export async function listModes() {
  return apiRequest<{ modes: ModeCatalogItem[] }>('/modes');
}

export async function generateMode(
  token: string,
  input: { description: string; provider?: string; model?: string },
) {
  // 后端返回 {ok, mode_def, warning}；unwrap 成直接返回 mode_def
  return apiRequest<CustomModeDefinition>('/modes/generate', {
    method: 'POST',
    token,
    body: input,
  }).then((result) => {
    const wrapped = result as { ok?: boolean; mode_def?: CustomModeDefinition; warning?: string };
    if (wrapped.mode_def) {
      return wrapped.mode_def;
    }
    // 旧版/降级兼容：假设直接就是 CustomModeDefinition
    return result;
  });
}

export async function saveCustomMode(token: string, modeDef: CustomModeDefinition, mac?: string) {
  return apiRequest<{ ok: boolean; mode_id: string }>('/modes/custom', {
    method: 'POST',
    token,
    body: { ...modeDef, ...(mac ? { mac } : {}) },
  });
}

export async function getCustomMode(token: string, modeId: string) {
  return apiRequest<CustomModeDefinition>(`/modes/custom/${encodeURIComponent(modeId)}`, {
    token,
  });
}

export function buildStaticModeDefinition(input: {
  modeId: string;
  displayName: string;
  description: string;
  text: string;
}): CustomModeDefinition {
  const modeId = input.modeId.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_') || 'CUSTOM_MODE';
  const displayName = input.displayName.trim() || modeId;
  const description = input.description.trim() || 'Created from InkSight mobile editor';
  const text = input.text.trim() || 'Stay with one thing.';

  return {
    mode_id: modeId,
    display_name: displayName,
    icon: 'star',
    cacheable: true,
    description,
    content: {
      type: 'static',
      static_data: {
        text,
      },
    },
    layout: {
      status_bar: {
        line_width: 1,
      },
      body: [
        {
          type: 'centered_text',
          field: 'text',
          font: 'noto_serif_regular',
          font_size: 18,
          vertical_center: true,
        },
      ],
      footer: {
        label: displayName.slice(0, 12).toUpperCase(),
      },
    },
  };
}
