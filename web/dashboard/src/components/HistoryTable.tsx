import { Clock, TrendingUp, TrendingDown, BarChart3 } from 'lucide-react';
import { useState } from 'react';

interface HistoryItem {
  id: string;
  timestamp: string;
  parameters: Record<string, any>;
  metrics: Record<string, number>;
  status: 'success' | 'failed' | 'running';
}

interface HistoryTableProps {
  items: HistoryItem[];
  metricColumns: { key: string; label: string; format?: (value: number) => string }[];
  onSelect?: (item: HistoryItem) => void;
  onCompare?: (items: HistoryItem[]) => void;
}

export function HistoryTable({ items, metricColumns, onSelect, onCompare }: HistoryTableProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [compareMode, setCompareMode] = useState(false);

  const toggleSelection = (id: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const handleCompare = () => {
    const selectedItems = items.filter(item => selectedIds.has(item.id));
    onCompare?.(selectedItems);
  };

  const handleRowClick = (item: HistoryItem) => {
    if (compareMode) {
      toggleSelection(item.id);
    } else {
      onSelect?.(item);
    }
  };
  if (items.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <Clock className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>실행 히스토리가 없습니다</p>
        <p className="text-sm mt-2">파라미터를 설정하고 실행해보세요</p>
      </div>
    );
  }

  const formatValue = (value: number, format?: (value: number) => string) => {
    if (format) return format(value);
    return value.toFixed(2);
  };

  const getStatusBadge = (status: string) => {
    const badges = {
      success: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      running: 'bg-blue-100 text-blue-800',
    };
    return badges[status as keyof typeof badges] || badges.success;
  };

  const getStatusText = (status: string) => {
    const texts = {
      success: '완료',
      failed: '실패',
      running: '실행 중',
    };
    return texts[status as keyof typeof texts] || status;
  };

  return (
    <div className="space-y-4">
      {onCompare && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setCompareMode(!compareMode);
                setSelectedIds(new Set());
              }}
              className={`px-4 py-2 rounded-lg border ${
                compareMode
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              <BarChart3 className="h-4 w-4 inline mr-2" />
              {compareMode ? '비교 모드 종료' : '비교 모드'}
            </button>
            {compareMode && (
              <span className="text-sm text-gray-600">
                {selectedIds.size}개 선택됨
              </span>
            )}
          </div>
          {compareMode && selectedIds.size >= 2 && (
            <button
              onClick={handleCompare}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
            >
              선택한 항목 비교 ({selectedIds.size}개)
            </button>
          )}
        </div>
      )}
      <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b">
            {compareMode && <th className="text-left p-3 w-12">선택</th>}
            <th className="text-left p-3">실행 시간</th>
            <th className="text-left p-3">상태</th>
            {metricColumns.map(col => (
              <th key={col.key} className="text-right p-3">{col.label}</th>
            ))}
            <th className="text-left p-3">주요 파라미터</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => {
            const isFirst = index === 0;
            const prevItem = index > 0 ? items[index - 1] : null;
            
            return (
              <tr
                key={item.id}
                onClick={() => handleRowClick(item)}
                className={`border-b hover:bg-gray-50 cursor-pointer ${
                  isFirst && !compareMode ? 'bg-blue-50' : ''
                } ${
                  selectedIds.has(item.id) ? 'bg-green-50' : ''
                }`}
              >
                {compareMode && (
                  <td className="p-3">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(item.id)}
                      onChange={() => toggleSelection(item.id)}
                      onClick={(e) => e.stopPropagation()}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                  </td>
                )}
                <td className="p-3 text-sm text-gray-600">
                  {new Date(item.timestamp).toLocaleString('ko-KR')}
                  {isFirst && (
                    <span className="ml-2 text-xs bg-blue-600 text-white px-2 py-1 rounded">
                      최신
                    </span>
                  )}
                </td>
                <td className="p-3">
                  <span className={`text-xs px-2 py-1 rounded ${getStatusBadge(item.status)}`}>
                    {getStatusText(item.status)}
                  </span>
                </td>
                {metricColumns.map(col => {
                  const value = item.metrics[col.key];
                  const prevValue = prevItem?.metrics[col.key];
                  const isImproved = prevValue !== undefined && value > prevValue;
                  const isWorse = prevValue !== undefined && value < prevValue;
                  
                  return (
                    <td key={col.key} className="p-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <span className={`font-medium ${
                          isImproved ? 'text-green-600' : isWorse ? 'text-red-600' : ''
                        }`}>
                          {formatValue(value, col.format)}
                        </span>
                        {isImproved && <TrendingUp className="h-4 w-4 text-green-600" />}
                        {isWorse && <TrendingDown className="h-4 w-4 text-red-600" />}
                      </div>
                    </td>
                  );
                })}
                <td className="p-3 text-sm text-gray-600">
                  {Object.entries(item.parameters)
                    .slice(0, 3)
                    .map(([key, value]) => `${key}: ${value}`)
                    .join(', ')}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>
    </div>
  );
}
