import { X } from 'lucide-react';
import { useState, useEffect } from 'react';
import { HistoryTable } from './HistoryTable';

interface ParameterField {
  name: string;
  label: string;
  type: 'number' | 'text' | 'select';
  value: any;
  options?: { label: string; value: any }[];
  min?: number;
  max?: number;
  step?: number;
}

interface ParameterModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  fields: ParameterField[];
  presets?: { name: string; label: string; description: string }[];
  history?: any[];
  historyMetricColumns?: { key: string; label: string; format?: (value: number) => string }[];
  onSave: (params: Record<string, any>) => void;
  onApplyPreset?: (presetName: string) => void;
  onSelectHistory?: (item: any) => void;
}

export function ParameterModal({
  isOpen,
  onClose,
  title,
  fields,
  presets,
  history,
  historyMetricColumns,
  onSave,
  onApplyPreset,
  onSelectHistory,
}: ParameterModalProps) {
  const [params, setParams] = useState<Record<string, any>>({});
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    if (isOpen) {
      const initialParams: Record<string, any> = {};
      fields.forEach(field => {
        initialParams[field.name] = field.value;
      });
      setParams(initialParams);
    }
  }, [isOpen, fields]);

  if (!isOpen) return null;

  const handleChange = (name: string, value: any) => {
    setParams(prev => ({ ...prev, [name]: value }));
  };

  const handleSave = () => {
    onSave(params);
    onClose();
  };

  const handleCancel = () => {
    // 변경사항 버리고 닫기
    onClose();
  };

  const handlePreset = (presetName: string) => {
    if (onApplyPreset) {
      onApplyPreset(presetName);
      // 프리셋 적용 후 모달 닫지 않음 (사용자가 확인 후 저장)
    }
  };

  const handleSelectHistory = (item: any) => {
    if (onSelectHistory) {
      onSelectHistory(item);
      // 히스토리 선택 시 파라미터 적용
      setParams(item.parameters);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b">
          <h2 className="text-2xl font-bold">{title}</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-180px)]">
          {/* Presets */}
          {presets && presets.length > 0 && (
            <div className="mb-6">
              <h3 className="text-lg font-semibold mb-3">프리셋</h3>
              <div className="grid grid-cols-3 gap-3">
                {presets.map(preset => (
                  <button
                    key={preset.name}
                    onClick={() => handlePreset(preset.name)}
                    className="p-4 border-2 border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-colors text-left"
                  >
                    <div className="font-semibold mb-1">{preset.label}</div>
                    <div className="text-sm text-gray-600">{preset.description}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* History */}
          {history && history.length > 0 && (
            <div className="mb-6">
              <div className="flex justify-between items-center mb-3">
                <h3 className="text-lg font-semibold">히스토리</h3>
                <button
                  onClick={() => setShowHistory(!showHistory)}
                  className="text-sm text-blue-600 hover:text-blue-700"
                >
                  {showHistory ? '숨기기' : '보기'}
                </button>
              </div>
              {showHistory && historyMetricColumns && (
                <HistoryTable
                  items={history}
                  metricColumns={historyMetricColumns}
                  onSelect={handleSelectHistory}
                />
              )}
            </div>
          )}

          {/* Parameters */}
          <div>
            <h3 className="text-lg font-semibold mb-3">파라미터 설정</h3>
            <div className="grid grid-cols-2 gap-4">
              {fields.map(field => (
                <div key={field.name}>
                  <label className="block text-sm font-medium mb-2">
                    {field.label}
                  </label>
                  {field.type === 'select' ? (
                    <select
                      value={params[field.name] || field.value}
                      onChange={(e) => handleChange(field.name, e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      {field.options?.map(option => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  ) : field.type === 'number' ? (
                    <input
                      type="number"
                      value={params[field.name] ?? field.value}
                      onChange={(e) => handleChange(field.name, parseFloat(e.target.value))}
                      min={field.min}
                      max={field.max}
                      step={field.step}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  ) : (
                    <input
                      type="text"
                      value={params[field.name] || field.value}
                      onChange={(e) => handleChange(field.name, e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-6 border-t bg-gray-50">
          <button
            onClick={handleCancel}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-100"
          >
            취소
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            저장 및 적용
          </button>
        </div>
      </div>
    </div>
  );
}
