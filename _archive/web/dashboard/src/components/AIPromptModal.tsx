import { useState } from 'react';
import { X, Copy, Check, ExternalLink } from 'lucide-react';

interface AIPromptModalProps {
  isOpen: boolean;
  onClose: () => void;
  prompt: string;
  title: string;
}

export function AIPromptModal({ isOpen, onClose, prompt, title }: AIPromptModalProps) {
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('클립보드 복사 실패:', err);
    }
  };

  const openChatGPT = () => {
    window.open('https://chat.openai.com/', '_blank');
  };

  const openGemini = () => {
    window.open('https://gemini.google.com/', '_blank');
  };

  const openClaude = () => {
    window.open('https://claude.ai/', '_blank');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col">
        {/* 헤더 */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-2xl font-bold">{title}</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 프롬프트 미리보기 */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
            <pre className="text-sm whitespace-pre-wrap font-mono text-gray-800">
              {prompt}
            </pre>
          </div>
        </div>

        {/* 액션 버튼 */}
        <div className="p-6 border-t bg-gray-50 space-y-3">
          {/* 복사 버튼 */}
          <button
            onClick={handleCopy}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            {copied ? (
              <>
                <Check className="w-5 h-5" />
                <span>✅ 클립보드에 복사됨!</span>
              </>
            ) : (
              <>
                <Copy className="w-5 h-5" />
                <span>📋 클립보드에 복사</span>
              </>
            )}
          </button>

          {/* AI 서비스 링크 */}
          <div className="grid grid-cols-3 gap-3">
            <button
              onClick={openChatGPT}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              <span>ChatGPT</span>
            </button>
            <button
              onClick={openGemini}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              <span>Gemini</span>
            </button>
            <button
              onClick={openClaude}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors"
            >
              <ExternalLink className="w-4 h-4" />
              <span>Claude</span>
            </button>
          </div>

          {/* 사용 안내 */}
          <div className="text-sm text-gray-600 bg-blue-50 p-3 rounded-lg">
            <p className="font-medium mb-1">💡 사용 방법:</p>
            <ol className="list-decimal list-inside space-y-1">
              <li>"클립보드에 복사" 버튼을 클릭하세요</li>
              <li>원하는 AI 서비스 버튼을 클릭하여 새 탭에서 열기</li>
              <li>AI 채팅창에 복사한 프롬프트를 붙여넣기 (Ctrl+V)</li>
              <li>AI의 분석과 조언을 확인하세요</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
}
