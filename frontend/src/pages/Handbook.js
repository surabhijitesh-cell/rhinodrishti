import { useState, useEffect } from "react";
import axios from "axios";
import { BookOpen } from "lucide-react";

export default function Handbook({ api }) {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${api}/handbook`).then(res => {
      setContent(res.data.content || "");
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [api]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="handbook-page">
        <span className="font-mono text-xs text-muted-foreground">Loading handbook...</span>
      </div>
    );
  }

  // Simple markdown to HTML renderer for the handbook
  const renderMarkdown = (md) => {
    let html = md
      // Headers
      .replace(/^### (.+)$/gm, '<h3 class="text-base font-mono font-bold mt-6 mb-2 text-foreground">$1</h3>')
      .replace(/^## (\d+\. .+)$/gm, '<h2 id="$1" class="text-lg font-mono font-bold mt-8 mb-3 pt-4 border-t border-border/40 text-foreground">$1</h2>')
      .replace(/^## (.+)$/gm, '<h2 class="text-lg font-mono font-bold mt-8 mb-3 pt-4 border-t border-border/40 text-foreground">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-mono font-bold mb-4 text-foreground">$1</h1>')
      // Links [text](url)
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<span class="text-primary">$1</span>')
      // Bold
      .replace(/\*\*(.+?)\*\*/g, '<strong class="text-foreground">$1</strong>')
      // Inline code
      .replace(/`(.+?)`/g, '<code class="bg-muted/50 px-1 py-0.5 text-[11px] font-mono text-primary">$1</code>')
      // Tables
      .replace(/^\|(.+)\|$/gm, (match) => {
        const cells = match.split('|').filter(c => c.trim());
        if (cells.every(c => /^[\s-:]+$/.test(c))) return '';
        const isHeader = cells.some(c => c.includes('---'));
        if (isHeader) return '';
        const tag = 'td';
        const cellHtml = cells.map(c => `<${tag} class="px-3 py-1.5 border border-border/30 text-xs font-mono">${c.trim()}</${tag}>`).join('');
        return `<tr>${cellHtml}</tr>`;
      })
      // Unordered lists
      .replace(/^- (.+)$/gm, '<li class="text-xs text-muted-foreground font-mono ml-4 mb-1 list-disc">$1</li>')
      // Ordered lists
      .replace(/^\d+\. (.+)$/gm, '<li class="text-xs text-muted-foreground font-mono ml-4 mb-1 list-decimal">$1</li>')
      // Code blocks
      .replace(/```[\s\S]*?```/g, (match) => {
        const code = match.replace(/```\w*\n?/g, '').replace(/```/g, '');
        return `<pre class="bg-muted/30 border border-border/30 p-3 my-3 overflow-x-auto"><code class="text-[10px] font-mono text-muted-foreground whitespace-pre">${code}</code></pre>`;
      })
      // Horizontal rules
      .replace(/^---$/gm, '<hr class="border-border/40 my-6" />')
      // Paragraphs (lines that aren't already HTML)
      .replace(/^(?!<[hluotp]|<hr|<pre|<code|<li|<tr)(.+)$/gm, '<p class="text-xs text-muted-foreground font-mono mb-2 leading-relaxed">$1</p>');

    // Wrap table rows
    html = html.replace(/(<tr>[\s\S]*?<\/tr>\n?)+/g, (match) => {
      return `<table class="w-full border-collapse my-3">${match}</table>`;
    });

    return html;
  };

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto" data-testid="handbook-page">
      <div className="flex items-center gap-2 mb-6">
        <BookOpen size={24} className="text-primary" />
        <h1 className="font-mono text-2xl font-bold tracking-tight">User Handbook</h1>
      </div>
      <div
        className="prose prose-sm max-w-none"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
      />
    </div>
  );
}
