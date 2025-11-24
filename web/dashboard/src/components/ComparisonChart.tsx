import { X } from 'lucide-react';

interface ComparisonItem {
  id: string;
  timestamp: string;
  parameters: Record<string, any>;
  metrics: Record<string, number>;
}

interface ComparisonChartProps {
  isOpen: boolean;
  onClose: () => void;
  items: ComparisonItem[];
  metricColumns: { key: string; label: string; format?: (value: number) => string }[];
  title: string;
}

export function ComparisonChart({ isOpen, onClose, items, metricColumns, title }: ComparisonChartProps) {
  if (!isOpen) return null;

  const getColor = (index: number) => {
    const colors = [
      'bg-blue-500',
      'bg-green-500',
      'bg-purple-500',
      'bg-orange-500',
      'bg-pink-500',
      'bg-indigo-500',
    ];
    return colors[index % colors.length];
  };

  const getTextColor = (index: number) => {
    const colors = [
      'text-blue-600',
      'text-green-600',
      'text-purple-600',
      'text-orange-600',
      'text-pink-600',
      'text-indigo-600',
    ];
    return colors[index % colors.length];
  };

  const formatValue = (value: number, format?: (value: number) => string) => {
    if (format) return format(value);
    return value.toFixed(2);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
          <h2 className="text-2xl font-bold">{title}</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* 범례 */}
          <div className="flex flex-wrap gap-4">
            {items.map((item, index) => (
              <div key={item.id} className="flex items-center gap-2">
                <div className={`w-4 h-4 rounded ${getColor(index)}`} />
                <span className="text-sm font-medium">
                  {new Date(item.timestamp).toLocaleString('ko-KR', {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
            ))}
          </div>

          {/* 성과 지표 비교 */}
          <div>
            <h3 className="text-lg font-bold mb-4">성과 지표 비교</h3>
            <div className="space-y-6">
              {metricColumns.map(col => {
                const values = items.map(item => item.metrics[col.key]);
                const maxValue = Math.max(...values);
                const minValue = Math.min(...values);
                
                return (
                  <div key={col.key}>
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-medium">{col.label}</span>
                      <span className="text-sm text-gray-500">
                        최고: {formatValue(maxValue, col.format)} / 최저: {formatValue(minValue, col.format)}
                      </span>
                    </div>
                    <div className="space-y-2">
                      {items.map((item, index) => {
                        const value = item.metrics[col.key];
                        const percentage = maxValue > 0 ? (Math.abs(value) / Math.abs(maxValue)) * 100 : 0;
                        const isBest = value === maxValue;
                        
                        return (
                          <div key={item.id} className="flex items-center gap-3">
                            <div className={`w-4 h-4 rounded ${getColor(index)} flex-shrink-0`} />
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <div className="flex-1 bg-gray-100 rounded-full h-8 relative">
                                  <div
                                    className={`${getColor(index)} h-8 rounded-full flex items-center justify-end pr-3 transition-all`}
                                    style={{ width: `${percentage}%` }}
                                  >
                                    <span className="text-white text-sm font-medium">
                                      {formatValue(value, col.format)}
                                    </span>
                                  </div>
                                </div>
                                {isBest && (
                                  <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded font-medium">
                                    최고
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 파라미터 비교 */}
          <div>
            <h3 className="text-lg font-bold mb-4">파라미터 비교</h3>
            <div className="overflow-x-auto">
              <table className="w-full border">
                <thead>
                  <tr className="bg-gray-50 border-b">
                    <th className="text-left p-3 font-medium">파라미터</th>
                    {items.map((item, index) => (
                      <th key={item.id} className={`text-right p-3 font-medium ${getTextColor(index)}`}>
                        실행 #{items.length - index}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(items[0]?.parameters || {}).map(paramKey => (
                    <tr key={paramKey} className="border-b">
                      <td className="p-3 font-medium text-gray-700">{paramKey}</td>
                      {items.map(item => {
                        const value = item.parameters[paramKey];
                        return (
                          <td key={item.id} className="p-3 text-right">
                            {typeof value === 'number' ? value.toFixed(4) : String(value)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 개선/악화 분석 */}
          <div>
            <h3 className="text-lg font-bold mb-4">변화 분석</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {metricColumns.map(col => {
                const values = items.map(item => item.metrics[col.key]);
                const firstValue = values[values.length - 1];
                const lastValue = values[0];
                const change = lastValue - firstValue;
                const changePercent = firstValue !== 0 ? (change / Math.abs(firstValue)) * 100 : 0;
                const isImproved = change > 0;
                
                return (
                  <div key={col.key} className="p-4 border rounded-lg">
                    <div className="text-sm text-gray-600 mb-1">{col.label}</div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-2xl font-bold">
                        {formatValue(lastValue, col.format)}
                      </span>
                      <span className={`text-sm font-medium ${
                        isImproved ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {isImproved ? '+' : ''}{change.toFixed(2)} ({changePercent.toFixed(1)}%)
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      초기값: {formatValue(firstValue, col.format)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="sticky bottom-0 bg-gray-50 border-t px-6 py-4 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}
