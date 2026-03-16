import { apiRequest } from '@/lib/api-client';

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

export async function listModes() {
  return apiRequest<{ modes: ModeCatalogItem[] }>('/modes');
}

export async function generateMode(
  token: string,
  input: { description: string; provider?: string; model?: string },
) {
  return apiRequest<CustomModeDefinition>('/modes/generate', {
    method: 'POST',
    token,
    body: input,
  });
}

export async function saveCustomMode(token: string, modeDef: CustomModeDefinition) {
  return apiRequest<{ ok: boolean; mode_id: string }>('/modes/custom', {
    method: 'POST',
    token,
    body: modeDef,
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
