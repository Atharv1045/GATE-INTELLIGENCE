import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { Check, Copy, AlertTriangle } from 'lucide-react';

interface CodeBlockProps {
  className?: string;
  children?: React.ReactNode;
}

const CodeBlock: React.FC<CodeBlockProps> = ({ className, children }) => {
  const [copied, setCopied] = useState(false);
  const match = /language-([\w+-]+)/.exec(className || '');
  const codeString = String(children || '').replace(/\n$/, '');
  const isInline = !match && !codeString.includes('\n');

  if (isInline) {
    return (
      <code className="bg-[#1C2541] text-amber-300 px-1.5 py-0.5 rounded font-mono text-xs border border-slate-700/60 break-words">
        {children}
      </code>
    );
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(codeString);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback if clipboard API is restricted
      const textarea = document.createElement('textarea');
      textarea.value = codeString;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const languageLabel = match ? match[1].toUpperCase() : 'CODE';

  return (
    <div className="my-4 rounded-xl border border-slate-800 bg-[#070D1E] overflow-hidden shadow-lg">
      <div className="flex items-center justify-between px-4 py-2 bg-[#10182E] border-b border-slate-800/80 text-xs text-slate-400">
        <span className="font-mono uppercase font-semibold text-indigo-300 tracking-wider">
          {languageLabel}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#1C2541] hover:bg-[#2A375E] text-slate-300 hover:text-white transition-colors text-xs font-medium"
          title="Copy code to clipboard"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400 text-[11px] font-medium">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span className="text-[11px]">Copy</span>
            </>
          )}
        </button>
      </div>
      <div className="p-4 overflow-x-auto text-xs sm:text-sm font-mono text-slate-100 leading-relaxed scrollbar-thin">
        <pre className="m-0 p-0 bg-transparent font-mono">
          <code>{children}</code>
        </pre>
      </div>
    </div>
  );
};

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallbackText: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

export class MarkdownErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Markdown rendering error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-amber-400 text-xs bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 rounded-lg">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>Notice: Rendered in safe plain-text mode due to a formatting error.</span>
          </div>
          <pre className="whitespace-pre-wrap font-sans text-sm text-slate-200 leading-relaxed bg-[#070D1E] p-4 rounded-lg border border-slate-800">
            {this.props.fallbackText}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = '' }) => {
  return (
    <MarkdownErrorBoundary fallbackText={content}>
      <div className={`prose-gate text-slate-200 text-sm leading-relaxed ${className}`}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[
            [
              rehypeKatex,
              {
                strict: false,
                errorColor: '#f87171',
              },
            ],
          ]}
          components={{
            // Pass-through pre so CodeBlock handles code blocks directly
            pre: ({ children }) => <>{children}</>,
            code: CodeBlock,
            h1: ({ children }) => (
              <h1 className="text-2xl font-bold text-white border-b border-indigo-500/30 pb-2 mt-6 mb-3 first:mt-0">
                {children}
              </h1>
            ),
            h2: ({ children }) => (
              <h2 className="text-xl font-bold text-indigo-300 border-b border-slate-800/80 pb-1.5 mt-5 mb-2.5 first:mt-0">
                {children}
              </h2>
            ),
            h3: ({ children }) => (
              <h3 className="text-lg font-semibold text-sky-300 mt-4 mb-2 first:mt-0">
                {children}
              </h3>
            ),
            h4: ({ children }) => (
              <h4 className="text-base font-semibold text-slate-200 mt-3 mb-1.5 first:mt-0">
                {children}
              </h4>
            ),
            h5: ({ children }) => (
              <h5 className="text-sm font-semibold text-slate-300 mt-2.5 mb-1 first:mt-0">
                {children}
              </h5>
            ),
            h6: ({ children }) => (
              <h6 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mt-2 mb-1 first:mt-0">
                {children}
              </h6>
            ),
            p: ({ children }) => (
              <p className="mb-3 leading-relaxed text-slate-200 last:mb-0">
                {children}
              </p>
            ),
            strong: ({ children }) => (
              <strong className="font-semibold text-white">
                {children}
              </strong>
            ),
            em: ({ children }) => (
              <em className="italic text-slate-300">
                {children}
              </em>
            ),
            blockquote: ({ children }) => (
              <blockquote className="border-l-4 border-indigo-500 bg-[#1C2541]/40 rounded-r-lg px-4 py-2.5 my-3 text-slate-300 italic">
                {children}
              </blockquote>
            ),
            ul: ({ children }) => (
              <ul className="list-disc list-outside ml-6 space-y-1.5 my-2.5 text-slate-200 marker:text-indigo-400">
                {children}
              </ul>
            ),
            ol: ({ children }) => (
              <ol className="list-decimal list-outside ml-6 space-y-1.5 my-2.5 text-slate-200 marker:text-indigo-400">
                {children}
              </ol>
            ),
            li: ({ children }) => (
              <li className="leading-relaxed text-slate-200 pl-1">
                {children}
              </li>
            ),
            hr: () => <hr className="border-t border-slate-800 my-5" />,
            a: ({ href, children }) => (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2 transition-colors"
              >
                {children}
              </a>
            ),
            table: ({ children }) => (
              <div className="overflow-x-auto my-4 rounded-xl border border-slate-800 bg-[#0B132B]/60 shadow-md">
                <table className="min-w-full divide-y divide-slate-800 text-left text-sm text-slate-200">
                  {children}
                </table>
              </div>
            ),
            thead: ({ children }) => (
              <thead className="bg-[#1C2541]/90 text-xs font-semibold text-indigo-300 uppercase tracking-wider">
                {children}
              </thead>
            ),
            tbody: ({ children }) => (
              <tbody className="divide-y divide-slate-800/60 bg-[#0B132B]/40">
                {children}
              </tbody>
            ),
            tr: ({ children }) => (
              <tr className="hover:bg-[#1C2541]/30 transition-colors">
                {children}
              </tr>
            ),
            th: ({ children }) => (
              <th className="px-4 py-3 border-b border-slate-700/80 font-semibold text-indigo-300 text-xs tracking-wider">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="px-4 py-2.5 text-slate-200 align-top border-b border-slate-800/40 text-xs sm:text-sm">
                {children}
              </td>
            ),
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    </MarkdownErrorBoundary>
  );
};
