import { useState, useEffect } from "react";
import {
  BarChart3, Brain, ShieldAlert, TrendingDown, TrendingUp,
  Gauge, Users, Star, AlertTriangle, Target, RefreshCw
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Progress } from "../components/ui/progress";
import { toast } from "sonner";
import axios from "axios";

const CONFIDENCE_COLORS = {
  HIGH: "text-emerald-400",
  MODERATE: "text-blue-400",
  LOW: "text-yellow-400",
  INSUFFICIENT_DATA: "text-muted-foreground",
};

export default function TrainingSummary({ api }) {
  const [stats, setStats] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsRes, profileRes] = await Promise.all([
        axios.get(`${api}/feedback/stats`),
        axios.get(`${api}/feedback/training-profile`),
      ]);
      setStats(statsRes.data);
      setProfile(profileRes.data);
    } catch (e) {
      console.error("Failed to load training data:", e);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, [api]);

  if (loading) {
    return (
      <div className="space-y-6" data-testid="training-summary-page">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']">
            Training & Feedback
          </h1>
          <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
            Loading collective intelligence...
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="border border-border bg-card p-6 h-32 animate-pulse">
              <div className="h-4 bg-muted rounded w-1/2 mb-3" />
              <div className="h-8 bg-muted rounded w-1/3" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const maxRating = stats?.distribution ? Math.max(...Object.values(stats.distribution), 1) : 1;

  return (
    <div className="space-y-6" data-testid="training-summary-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold uppercase tracking-tight font-['Barlow_Condensed']" data-testid="training-title">
            Training & Feedback
          </h1>
          <p className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground mt-1">
            Alpha Controlled Intelligence Learning System
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="rounded-none uppercase text-xs tracking-wider"
          onClick={fetchData}
          data-testid="refresh-training-btn"
        >
          <RefreshCw size={14} className="mr-1.5" /> Refresh
        </Button>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="border border-border rounded-none bg-card" data-testid="stat-total-feedback">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <BarChart3 size={14} className="text-primary" />
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Total Ratings</span>
            </div>
            <p className="text-2xl font-bold font-['Barlow_Condensed']">{stats?.total_feedback || 0}</p>
          </CardContent>
        </Card>

        <Card className="border border-border rounded-none bg-card" data-testid="stat-unique-items">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <Target size={14} className="text-blue-400" />
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Items Rated</span>
            </div>
            <p className="text-2xl font-bold font-['Barlow_Condensed']">{stats?.unique_items_rated || 0}</p>
          </CardContent>
        </Card>

        <Card className="border border-border rounded-none bg-card" data-testid="stat-analysts">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <Users size={14} className="text-emerald-400" />
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Analysts</span>
            </div>
            <p className="text-2xl font-bold font-['Barlow_Condensed']">{stats?.unique_devices || 0}</p>
          </CardContent>
        </Card>

        <Card className="border border-border rounded-none bg-card" data-testid="stat-global-avg">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <Star size={14} className="text-amber-400" />
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Avg Rating</span>
            </div>
            <p className="text-2xl font-bold font-['Barlow_Condensed']">{stats?.global_avg_rating?.toFixed(1) || "N/A"}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Confidence & Rating Distribution */}
        <Card className="border border-border rounded-none bg-card" data-testid="confidence-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <Gauge size={16} className="text-primary" />
              Confidence & Distribution
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-mono uppercase">Confidence Level</span>
              <Badge
                variant="outline"
                className={`rounded-none text-xs uppercase ${CONFIDENCE_COLORS[profile?.confidence_level] || ""}`}
                data-testid="confidence-level"
              >
                {profile?.confidence_level || "N/A"}
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground font-mono uppercase">Recency Ratio</span>
              <span className="text-xs font-mono">{((profile?.recency_ratio || 0) * 100).toFixed(0)}% recent</span>
            </div>

            <div className="space-y-2">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Rating Distribution</p>
              {stats?.distribution && Object.entries(stats.distribution).sort(([a], [b]) => Number(b) - Number(a)).map(([rating, count]) => (
                <div key={rating} className="flex items-center gap-2">
                  <span className="text-xs font-mono w-4 text-right">{rating}</span>
                  <Star size={10} className="text-amber-400" fill="currentColor" />
                  <div className="flex-1 h-2 bg-muted rounded-none overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all"
                      style={{ width: `${(count / maxRating) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono w-8 text-right text-muted-foreground">{count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Intelligence Bias - Positive Weights */}
        <Card className="border border-border rounded-none bg-card" data-testid="positive-weights-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <TrendingUp size={16} className="text-emerald-400" />
              Analyst Preferences (High-Rated)
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            {profile?.positive_weights?.regions && Object.keys(profile.positive_weights.regions).length > 0 ? (
              <>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-2">Preferred Regions</p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(profile.positive_weights.regions).map(([region, count]) => (
                      <Badge key={region} variant="outline" className="rounded-none text-[10px] text-emerald-400 border-emerald-500/30 px-2 py-0.5">
                        {region} ({count})
                      </Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-2">Preferred Threat Types</p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(profile.positive_weights.threat_categories || {}).map(([cat, count]) => (
                      <Badge key={cat} variant="outline" className="rounded-none text-[10px] text-blue-400 border-blue-500/30 px-2 py-0.5">
                        {cat} ({count})
                      </Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-2">Key Actors</p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(profile.positive_weights.actors || {}).map(([actor, count]) => (
                      <Badge key={actor} variant="outline" className="rounded-none text-[10px] text-purple-400 border-purple-500/30 px-2 py-0.5">
                        {actor} ({count})
                      </Badge>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No high-rated patterns detected yet. Submit ratings to build the intelligence profile.</p>
            )}
          </CardContent>
        </Card>

        {/* Noise Patterns - Negative Weights */}
        <Card className="border border-border rounded-none bg-card" data-testid="negative-weights-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <TrendingDown size={16} className="text-red-400" />
              Noise Patterns (Low-Rated)
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            {profile?.negative_weights?.regions && Object.keys(profile.negative_weights.regions).length > 0 ? (
              <>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-2">Low-Value Regions</p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(profile.negative_weights.regions).map(([region, count]) => (
                      <Badge key={region} variant="outline" className="rounded-none text-[10px] text-red-400 border-red-500/30 px-2 py-0.5">
                        {region} ({count})
                      </Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-2">Ignored Categories</p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(profile.negative_weights.threat_categories || {}).map(([cat, count]) => (
                      <Badge key={cat} variant="outline" className="rounded-none text-[10px] text-orange-400 border-orange-500/30 px-2 py-0.5">
                        {cat} ({count})
                      </Badge>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No low-rated noise patterns identified yet.</p>
            )}

            {profile?.noise_patterns && profile.noise_patterns.length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono mb-2">Sample Noise Items</p>
                <div className="space-y-1.5">
                  {profile.noise_patterns.slice(0, 5).map((item, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs text-muted-foreground">
                      <AlertTriangle size={10} className="text-red-400 shrink-0" />
                      <span className="truncate">{item.title}</span>
                      {item.category && (
                        <Badge variant="outline" className="rounded-none text-[9px] px-1 py-0 shrink-0">
                          {item.category}
                        </Badge>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top & Lowest Rated */}
        <Card className="border border-border rounded-none bg-card" data-testid="top-rated-card">
          <CardHeader className="py-3 px-4 border-b border-border">
            <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
              <Brain size={16} className="text-primary" />
              Top & Lowest Rated Intelligence
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 space-y-4">
            {stats?.top_rated_items && stats.top_rated_items.length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-emerald-400 font-mono mb-2">
                  Highest Rated
                </p>
                <div className="space-y-2">
                  {stats.top_rated_items.map((item, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <span className="text-amber-400 font-mono shrink-0">{item.avg_rating.toFixed(1)}</span>
                      <span className="text-muted-foreground truncate flex-1">{item.title}</span>
                      <Badge variant="outline" className="rounded-none text-[9px] px-1 py-0 shrink-0">
                        {item.total_ratings} ratings
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {stats?.lowest_rated_items && stats.lowest_rated_items.length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-red-400 font-mono mb-2 mt-4">
                  Lowest Rated
                </p>
                <div className="space-y-2">
                  {stats.lowest_rated_items.map((item, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <span className="text-red-400 font-mono shrink-0">{item.avg_rating.toFixed(1)}</span>
                      <span className="text-muted-foreground truncate flex-1">{item.title}</span>
                      <Badge variant="outline" className="rounded-none text-[9px] px-1 py-0 shrink-0">
                        {item.total_ratings} ratings
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(!stats?.top_rated_items || stats.top_rated_items.length === 0) && (
              <p className="text-sm text-muted-foreground">Need at least 2 ratings per item to show rankings.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Updated Intelligence Bias Formula */}
      <Card className="border border-border rounded-none bg-card" data-testid="scoring-formula-card">
        <CardHeader className="py-3 px-4 border-b border-border">
          <CardTitle className="text-sm uppercase tracking-wider font-['Barlow_Condensed'] font-semibold flex items-center gap-2">
            <ShieldAlert size={16} className="text-amber-400" />
            Scoring Integration
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="bg-muted/20 border border-border p-4 font-mono text-xs space-y-1">
            <p className="text-muted-foreground">// Final scoring formula:</p>
            <p className="text-primary">final_score = base_ai_score + training_bias + aggregated_feedback_bias</p>
            <p className="text-muted-foreground mt-2">// Where:</p>
            <p><span className="text-blue-400">base_ai_score</span> = Claude AI classification priority (0-100)</p>
            <p><span className="text-emerald-400">training_bias</span> = log(total_ratings + 1) * (avg_rating - 3.5)</p>
            <p><span className="text-amber-400">aggregated_feedback_bias</span> = confidence_factor * relevance_weight</p>
          </div>
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 border border-border">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">High Rated Items</p>
              <p className="text-lg font-bold font-['Barlow_Condensed'] text-emerald-400">{profile?.high_rated_count || 0}</p>
            </div>
            <div className="p-3 border border-border">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Low Rated Items</p>
              <p className="text-lg font-bold font-['Barlow_Condensed'] text-red-400">{profile?.low_rated_count || 0}</p>
            </div>
            <div className="p-3 border border-border">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Recent 7d</p>
              <p className="text-lg font-bold font-['Barlow_Condensed']">{stats?.recent_7d || 0}</p>
            </div>
            <div className="p-3 border border-border">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">Max Per Item</p>
              <p className="text-lg font-bold font-['Barlow_Condensed']">{stats?.max_feedback_per_item || 20}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
