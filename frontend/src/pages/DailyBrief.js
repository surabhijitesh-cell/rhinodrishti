import { useState, useEffect, Component } from "react";
import {
  FileText, RefreshCw, Calendar, Shield, Globe, AlertTriangle, Download,
  Newspaper, Twitter, Upload, ExternalLink
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import axios from "axios";

class BriefErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="text-center py-16 border border-border bg-card">
          <AlertTriangle size={40} className="mx-auto text-amber-400 mb-4" />
          <p className="text-muted-foreground text-sm mb-2">Failed to render the daily brief.</p>
          <p className="text-xs text-muted-foreground mb-4 font-mono">{String(this.state.error?.message || '').slice(0, 100)}</p>
          <Button onClick={() => { this.setState({ hasError: false }); window.location.reload(); }} className="rounded-none uppercase text-xs tracking-wider">
            Reload Page
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function DailyBrief({ api }) {
  const [brief, setBrief] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    fetchBrief();
  }, [api]);

  const fetchBrief = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${api}/daily-brief`);
      setBrief(res.data);
    } catch (e) {
      console.error("Failed to fetch brief:", e);
    }
    setLoading(false);
  };

  const generateBrief = async () => {
    setGenerating(true);
    try {
      await axios.post(`${api}/daily-brief`);
      setTimeout(async () => {
        await fetchBrief();
        setGenerating(false);
      }, 5000);
    } catch (e) {
      console.error("Failed to generate brief:", e);
      setGenerating(false);
    }
  };

  const downloadPDF = async () => {
    try {
      const dateParam = brief?.date || new Date().toISOString().split("T")[0];
      const res = await axios.get(`${api}/daily-brief/pdf?date=${dateParam}`, {
        responseType: "blob"
      });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `Rhino_Drishti_Brief_${dateParam}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error("PDF download failed:", e);
    }
  };

  // Safe string render helper - prevents React error #31
  const safeStr = (val) => {
    if (val === null || val === undefined) return '';
    if (typeof val === 'string') return val;
    if (typeof val === 'number' || typeof val === 'boolean') return String(val);
    return JSON.stringify(val);
  };

  // Helper to render a news item (string or object)
  const renderNewsItem = (item, index) => {
    if (!item) return null;
    if (typeof item === 'string') {
      return (
        <li key={index} className="brief-bullet">
          <span className="text-primary font-mono text-xs mt-0.5 shrink-0">{String(index + 1).padStart(2, '0')}.</span>
          <span className="text-sm">{item}</span>
        </li>
      );
    }
    if (typeof item !== 'object') {
      return (
        <li key={index} className="brief-bullet">
          <span className="text-primary font-mono text-xs mt-0.5 shrink-0">{String(index + 1).padStart(2, '0')}.</span>
          <span className="text-sm">{String(item)}</span>
        </li>
      );
    }
    // Object format with title, summary, source_url
    return (
      <li key={index} className="border-b border-border/50 pb-3 last:border-0 last:pb-0">
        <div className="flex items-start gap-2">
          <span className="text-primary font-mono text-xs mt-1 shrink-0">{String(index + 1).padStart(2, '0')}.</span>
          <div className="flex-1">
            <p className="text-sm font-medium">{safeStr(item.title)}</p>
            {item.summary && (
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{safeStr(item.summary)}</p>
            )}
            <div className="flex items-center gap-3 mt-1">
              {item.source_url && (
                <a 
                  href={safeStr(item.source_url)} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline flex items-center gap-1"
                >
                  <ExternalLink size={10} />
                  Source
                </a>
              )}
              {item.state && (
                <Badge variant="outline" className="text-[9px] rounded-none px-1 py-0">{safeStr(item.state)}</Badge>
              )}
              {item.severity && item.severity !== 'low' && (
                <Badge className={`text-[9px] rounded-none px-1 py-0 ${
                  item.severity === 'critical' ? 'bg-red-500' : 
                  item.severity === 'high' ? 'bg-orange-500' : 'bg-yellow-500'
                }`}>{safeStr(item.severity)}</Badge>
              )}
            </div>
          </div>
        </div>
      </li>
    );
  };

  if (loading) {
    return (
      <div className="space-y-4" data-testid="daily-brief-loading">
        <div className="h-10 bg-muted animate-pulse w-1/2" />
        <div className="h-6 bg-muted animate-pulse w-1/3" />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="border border-border bg-card p-4 animate-pulse">
            <div className="h-4 bg-muted w-1/4 mb-3" />
            <div className="h-3 bg-muted w-full mb-2" />
            <div className="h-3 bg-muted w-5/6 mb-2" />
            <div className="h-3 bg-muted w-3/4" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <BriefErrorBoundary>
    <div className="space-y-6" data-testid="daily-brief-page">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="brief-title">
            Daily Intelligence Brief
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <Calendar size={12} className="text-muted-foreground" />
            <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground">
              {brief?.date || new Date().toISOString().split("T")[0]}
            </p>
            {brief?.generated_at && (
              <>
                <span className="text-muted-foreground">|</span>
                <p className="text-xs font-mono text-muted-foreground">
                  Generated: {new Date(brief.generated_at).toLocaleTimeString("en-IN")}
                </p>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {brief && (
            <Button
              variant="outline"
              onClick={downloadPDF}
              className="uppercase text-xs font-bold tracking-wider rounded-none"
              data-testid="download-pdf-btn"
            >
              <Download size={14} className="mr-2" />
              Export PDF
            </Button>
          )}
          <Button
            onClick={generateBrief}
            disabled={generating}
            className="uppercase text-xs font-bold tracking-wider rounded-none"
            data-testid="generate-brief-btn"
          >
            <RefreshCw size={14} className={`mr-2 ${generating ? "animate-spin" : ""}`} />
            {generating ? "Generating..." : "Regenerate Brief"}
          </Button>
        </div>
      </div>

      {brief ? (
        <div className="space-y-4">
          {/* Analyst Summary */}
          <Card className="border border-border rounded-none bg-card border-l-4 border-l-primary">
            <CardHeader className="py-3 px-4 border-b border-border">
              <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                <Shield size={16} className="text-primary" />
                Analyst Assessment
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4" data-testid="analyst-summary">
              <p className="text-sm leading-relaxed">{safeStr(brief.analyst_summary)}</p>
            </CardContent>
          </Card>

          {/* NER Key Developments */}
          <Card className="border border-border rounded-none bg-card">
            <CardHeader className="py-3 px-4 border-b border-border">
              <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                <AlertTriangle size={16} className="text-amber-400" />
                NER Key Developments
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4" data-testid="key-developments">
              {brief.key_developments && brief.key_developments.length > 0 ? (
                <ul className="space-y-3">
                  {brief.key_developments.map((dev, i) => renderNewsItem(dev, i))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No key developments recorded.</p>
              )}
            </CardContent>
          </Card>

          {/* National News Section */}
          {brief.national_news && brief.national_news.length > 0 && (
            <Card className="border border-border rounded-none bg-card">
              <CardHeader className="py-3 px-4 border-b border-border">
                <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                  <Newspaper size={16} className="text-blue-400" />
                  National News ({brief.national_news.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4" data-testid="national-news">
                <ul className="space-y-3">
                  {brief.national_news.map((news, i) => renderNewsItem(news, i))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* International News Section */}
          {brief.international_news && brief.international_news.length > 0 && (
            <Card className="border border-border rounded-none bg-card">
              <CardHeader className="py-3 px-4 border-b border-border">
                <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                  <Globe size={16} className="text-green-400" />
                  International News ({brief.international_news.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4" data-testid="international-news">
                <ul className="space-y-3">
                  {brief.international_news.map((news, i) => renderNewsItem(news, i))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Twitter/X Watch Section */}
          {brief.twitter_highlights && brief.twitter_highlights.length > 0 && (
            <Card className="border border-border rounded-none bg-card">
              <CardHeader className="py-3 px-4 border-b border-border">
                <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                  <Twitter size={16} className="text-[#1DA1F2]" />
                  X (Twitter) Watch ({brief.twitter_highlights.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4" data-testid="twitter-highlights">
                <ul className="space-y-3">
                  {brief.twitter_highlights.map((tweet, i) => (
                    <li key={i} className="border-b border-border/50 pb-3 last:border-0 last:pb-0">
                      <div className="flex items-start gap-2">
                        <span className="text-[#1DA1F2] font-mono text-xs mt-1">{String(i + 1).padStart(2, '0')}.</span>
                        <div>
                      <p className="text-sm font-medium">{safeStr(tweet.handle)} <span className="text-muted-foreground font-normal">({safeStr(tweet.account_name)})</span>
                          </p>
                          <p className="text-sm mt-1">{safeStr(tweet.tweet_text)}</p>
                          {tweet.tweet_url && (
                            <a href={tweet.tweet_url} target="_blank" rel="noopener noreferrer" 
                               className="text-xs text-primary hover:underline flex items-center gap-1 mt-1">
                              <ExternalLink size={10} />
                              View Tweet
                            </a>
                          )}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Uploaded Document Insights */}
          {brief.uploaded_insights && brief.uploaded_insights.length > 0 && (
            <Card className="border border-border rounded-none bg-card">
              <CardHeader className="py-3 px-4 border-b border-border">
                <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                  <Upload size={16} className="text-purple-400" />
                  Uploaded Document Insights ({brief.uploaded_insights.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4" data-testid="uploaded-insights">
                <ul className="space-y-3">
                  {brief.uploaded_insights.map((doc, i) => (
                    <li key={i} className="border-b border-border/50 pb-3 last:border-0 last:pb-0">
                      <p className="text-sm font-medium">{safeStr(doc.filename)}</p>
                      {doc.ai_analysis && (
                        <p className="text-xs text-muted-foreground mt-1">{safeStr(doc.ai_analysis)}</p>
                      )}
                      {doc.region && (
                        <Badge variant="outline" className="text-[9px] rounded-none px-1 py-0 mt-1">{safeStr(doc.region)}</Badge>
                      )}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* State-wise Highlights */}
          <Card className="border border-border rounded-none bg-card">
            <CardHeader className="py-3 px-4 border-b border-border">
              <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                <FileText size={16} className="text-primary" />
                State-wise Highlights
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4" data-testid="state-highlights">
              {brief.state_highlights && Object.keys(brief.state_highlights).length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {Object.entries(brief.state_highlights).map(([state, highlight]) => (
                    <div key={state} className="p-3 border border-border bg-background/50">
                      <Badge variant="outline" className="rounded-none uppercase text-[10px] tracking-wider mb-2">
                        {state}
                      </Badge>
                      <p className="text-sm text-muted-foreground leading-relaxed">{safeStr(highlight)}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No state-specific highlights available.</p>
              )}
            </CardContent>
          </Card>

          {/* Cross-Border Insights */}
          <Card className="border border-border rounded-none bg-card">
            <CardHeader className="py-3 px-4 border-b border-border">
              <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
                <Globe size={16} className="text-amber-400" />
                Cross-Border Insights
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4" data-testid="cross-border-insights">
              <p className="text-sm leading-relaxed">
                {safeStr(brief.cross_border_insights) || "No significant cross-border developments to report."}
              </p>
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="text-center py-16 border border-border bg-card">
          <FileText size={40} className="mx-auto text-muted-foreground mb-4" />
          <p className="text-muted-foreground text-sm mb-4">No daily brief available for today.</p>
          <Button onClick={generateBrief} disabled={generating} className="rounded-none uppercase text-xs tracking-wider" data-testid="generate-first-brief-btn">
            Generate Brief
          </Button>
        </div>
      )}
    </div>
    </BriefErrorBoundary>
  );
}
