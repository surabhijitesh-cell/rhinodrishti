import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Search, RefreshCw, Globe, Users, MapPin, ArrowRight, AlertTriangle, Network } from "lucide-react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";

const SEVERITY_COLORS = {
  critical: "bg-red-600 text-white",
  high: "bg-orange-600 text-white",
  medium: "bg-yellow-600 text-black",
  low: "bg-green-700 text-white",
};

function ActorCard({ actor, onSelect }) {
  const maxSev = ["critical", "high", "medium", "low"].find(s => (actor.severity_counts || {})[s] > 0) || "low";
  const topLocations = Object.entries(actor.locations || {}).sort((a, b) => b[1] - a[1]).slice(0, 4);
  const topThreats = Object.entries(actor.threat_types || {}).sort((a, b) => b[1] - a[1]).slice(0, 3);

  return (
    <div
      data-testid={`actor-card-${actor.name}`}
      className="bg-card/60 border border-border/50 p-4 cursor-pointer hover:border-primary/50 transition-colors"
      onClick={() => onSelect(actor.name)}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <Users size={14} className="text-primary" />
          <span className="font-mono text-sm font-semibold text-foreground">{actor.name}</span>
        </div>
        <div className="flex gap-1">
          <Badge className={`text-[9px] px-1 py-0 rounded-none ${SEVERITY_COLORS[maxSev]}`}>{maxSev}</Badge>
          {actor.is_cross_border && <Badge className="text-[9px] px-1 py-0 rounded-none bg-blue-700 text-white">CROSS-BORDER</Badge>}
        </div>
      </div>
      <div className="text-xs text-muted-foreground mb-2">
        {actor.activity_count} activities across {actor.article_count} articles
      </div>
      {topLocations.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {topLocations.map(([loc, count]) => (
            <span key={loc} className="text-[10px] bg-muted/50 px-1.5 py-0.5 font-mono">
              <MapPin size={9} className="inline mr-0.5" />{loc} ({count})
            </span>
          ))}
        </div>
      )}
      {topThreats.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {topThreats.map(([threat]) => (
            <span key={threat} className="text-[10px] text-primary/70 font-mono">{threat}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function LocationCard({ location }) {
  const topActors = Object.entries(location.actors || {}).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const maxSev = ["critical", "high", "medium", "low"].find(s => (location.severity_counts || {})[s] > 0) || "low";

  return (
    <div data-testid={`location-card-${location.name}`} className="bg-card/60 border border-border/50 p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <MapPin size={14} className="text-yellow-500" />
          <span className="font-mono text-sm font-semibold text-foreground">{location.name}</span>
        </div>
        <div className="flex gap-1">
          <Badge className={`text-[9px] px-1 py-0 rounded-none ${SEVERITY_COLORS[maxSev]}`}>{maxSev}</Badge>
          {location.is_border && <Badge className="text-[9px] px-1 py-0 rounded-none bg-red-800 text-white">BORDER</Badge>}
        </div>
      </div>
      <div className="text-xs text-muted-foreground mb-2">
        {location.activity_count} activities | States: {(location.states || []).join(", ")}
      </div>
      {topActors.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {topActors.map(([actor, count]) => (
            <span key={actor} className="text-[10px] bg-muted/50 px-1.5 py-0.5 font-mono">
              <Users size={9} className="inline mr-0.5" />{actor} ({count})
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function ActorDetail({ actor, edges, onBack }) {
  const relatedActors = Object.entries(actor.related_actors || {}).sort((a, b) => b[1] - a[1]).slice(0, 10);
  const locations = Object.entries(actor.locations || {}).sort((a, b) => b[1] - a[1]);
  const threats = Object.entries(actor.threat_types || {}).sort((a, b) => b[1] - a[1]);

  return (
    <div data-testid="actor-detail-view" className="space-y-4">
      <button onClick={onBack} className="text-xs text-muted-foreground hover:text-primary font-mono flex items-center gap-1">
        <ArrowRight size={12} className="rotate-180" /> Back to actors
      </button>
      <div className="bg-card/60 border border-border/50 p-5">
        <div className="flex items-center gap-3 mb-3">
          <Users size={20} className="text-primary" />
          <h2 className="font-mono text-lg font-bold">{actor.name}</h2>
          {actor.is_cross_border && <Badge className="text-[10px] px-1.5 py-0 rounded-none bg-blue-700 text-white">CROSS-BORDER</Badge>}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs mb-4">
          <div><span className="text-muted-foreground">Activities:</span> <span className="font-mono">{actor.activity_count}</span></div>
          <div><span className="text-muted-foreground">Articles:</span> <span className="font-mono">{actor.article_count}</span></div>
          <div><span className="text-muted-foreground">First seen:</span> <span className="font-mono">{(actor.first_seen || "").slice(0, 10)}</span></div>
          <div><span className="text-muted-foreground">Last seen:</span> <span className="font-mono">{(actor.last_seen || "").slice(0, 10)}</span></div>
        </div>
        {actor.countries?.length > 0 && (
          <div className="text-xs mb-3"><span className="text-muted-foreground">Countries:</span> {actor.countries.join(", ")}</div>
        )}
        {actor.aliases?.length > 1 && (
          <div className="text-xs mb-3"><span className="text-muted-foreground">Aliases:</span> {actor.aliases.join(", ")}</div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-card/60 border border-border/50 p-4">
          <h3 className="font-mono text-xs font-semibold mb-3 text-muted-foreground uppercase tracking-wider">Locations ({locations.length})</h3>
          <div className="space-y-1">
            {locations.map(([loc, count]) => (
              <div key={loc} className="flex justify-between text-xs">
                <span className="font-mono"><MapPin size={10} className="inline mr-1 text-yellow-500" />{loc}</span>
                <span className="text-muted-foreground">{count} events</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-card/60 border border-border/50 p-4">
          <h3 className="font-mono text-xs font-semibold mb-3 text-muted-foreground uppercase tracking-wider">Threat Types</h3>
          <div className="space-y-1">
            {threats.map(([threat, count]) => (
              <div key={threat} className="flex justify-between text-xs">
                <span className="font-mono"><AlertTriangle size={10} className="inline mr-1 text-orange-500" />{threat}</span>
                <span className="text-muted-foreground">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {relatedActors.length > 0 && (
        <div className="bg-card/60 border border-border/50 p-4">
          <h3 className="font-mono text-xs font-semibold mb-3 text-muted-foreground uppercase tracking-wider">Co-occurring Actors</h3>
          <div className="flex flex-wrap gap-2">
            {relatedActors.map(([name, count]) => (
              <span key={name} className="text-[10px] bg-primary/10 border border-primary/20 px-2 py-1 font-mono">
                {name} ({count})
              </span>
            ))}
          </div>
        </div>
      )}

      {edges.length > 0 && (
        <div className="bg-card/60 border border-border/50 p-4">
          <h3 className="font-mono text-xs font-semibold mb-3 text-muted-foreground uppercase tracking-wider">Movement Edges ({edges.length})</h3>
          <div className="space-y-2">
            {edges.map((edge, i) => (
              <div key={i} className="flex items-center gap-2 text-xs border-b border-border/30 pb-1">
                <span className="font-mono font-semibold text-primary">{edge.actor}</span>
                <ArrowRight size={10} className="text-muted-foreground" />
                <span className="font-mono text-yellow-500">{edge.location}</span>
                <span className="text-muted-foreground ml-auto">{edge.count}x</span>
                <span className="text-[10px] text-muted-foreground">
                  {Object.keys(edge.contexts || {}).join(", ")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {actor.sample_titles?.length > 0 && (
        <div className="bg-card/60 border border-border/50 p-4">
          <h3 className="font-mono text-xs font-semibold mb-3 text-muted-foreground uppercase tracking-wider">Related Articles</h3>
          <div className="space-y-1">
            {actor.sample_titles.map((t, i) => (
              <div key={i} className="text-xs text-muted-foreground font-mono">- {t}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function KnowledgeGraph({ api }) {
  const [stats, setStats] = useState(null);
  const [actors, setActors] = useState([]);
  const [locations, setLocations] = useState([]);
  const [activeTab, setActiveTab] = useState("actors");
  const [search, setSearch] = useState("");
  const [building, setBuilding] = useState(false);
  const [selectedActor, setSelectedActor] = useState(null);
  const [actorDetail, setActorDetail] = useState(null);
  const [actorEdges, setActorEdges] = useState([]);
  const [crossBorderOnly, setCrossBorderOnly] = useState(false);
  const [borderOnly, setBorderOnly] = useState(false);

  const fetchStats = useCallback(async () => {
    try {
      const res = await axios.get(`${api}/knowledge-graph/stats`);
      setStats(res.data);
    } catch (e) { console.error(e); }
  }, [api]);

  const fetchActors = useCallback(async () => {
    try {
      const params = { limit: 100 };
      if (crossBorderOnly) params.cross_border = true;
      const res = await axios.get(`${api}/knowledge-graph/actors`, { params });
      setActors(res.data.actors || []);
    } catch (e) { console.error(e); }
  }, [api, crossBorderOnly]);

  const fetchLocations = useCallback(async () => {
    try {
      const params = { limit: 100 };
      if (borderOnly) params.is_border = true;
      const res = await axios.get(`${api}/knowledge-graph/locations`, { params });
      setLocations(res.data.locations || []);
    } catch (e) { console.error(e); }
  }, [api, borderOnly]);

  const fetchActorDetail = useCallback(async (name) => {
    try {
      const res = await axios.get(`${api}/knowledge-graph/actors/${encodeURIComponent(name)}`);
      setActorDetail(res.data.actor);
      setActorEdges(res.data.edges || []);
      setSelectedActor(name);
    } catch (e) { console.error(e); }
  }, [api]);

  useEffect(() => { fetchStats(); }, [fetchStats]);
  useEffect(() => { fetchActors(); }, [fetchActors]);
  useEffect(() => { fetchLocations(); }, [fetchLocations]);

  const handleBuild = async () => {
    setBuilding(true);
    try {
      await axios.post(`${api}/knowledge-graph/build`);
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        await fetchStats();
        await fetchActors();
        await fetchLocations();
        if (attempts >= 6) {
          clearInterval(poll);
          setBuilding(false);
        }
      }, 3000);
    } catch (e) {
      console.error(e);
      setBuilding(false);
    }
  };

  const filteredActors = actors.filter(a =>
    !search || a.name.toLowerCase().includes(search.toLowerCase())
  );
  const filteredLocations = locations.filter(l =>
    !search || l.name.toLowerCase().includes(search.toLowerCase())
  );

  if (selectedActor && actorDetail) {
    return (
      <div className="space-y-4 p-4 md:p-6" data-testid="knowledge-graph-page">
        <ActorDetail actor={actorDetail} edges={actorEdges} onBack={() => { setSelectedActor(null); setActorDetail(null); }} />
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4 md:p-6" data-testid="knowledge-graph-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h1 className="font-mono text-2xl font-bold tracking-tight flex items-center gap-2">
            <Network size={24} className="text-primary" /> Knowledge Graph
          </h1>
          <p className="text-xs text-muted-foreground font-mono mt-1">
            Entity relationships across intelligence corpus
          </p>
        </div>
        <Button
          data-testid="rebuild-kg-btn"
          onClick={handleBuild}
          disabled={building}
          variant="outline"
          className="font-mono text-xs rounded-none"
        >
          <RefreshCw size={14} className={building ? "animate-spin mr-1" : "mr-1"} />
          {building ? "Building..." : "Rebuild Graph"}
        </Button>
      </div>

      {/* Stats bar */}
      {stats?.built && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="kg-stats">
          {[
            { label: "Actors", value: stats.actors, icon: Users },
            { label: "Locations", value: stats.locations, icon: MapPin },
            { label: "Edges", value: stats.edges, icon: ArrowRight },
            { label: "Cross-Border", value: stats.cross_border_actors, icon: Globe },
            { label: "Border Zones", value: stats.border_locations, icon: AlertTriangle },
          ].map(s => (
            <div key={s.label} className="bg-card/60 border border-border/50 p-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-mono flex items-center gap-1">
                <s.icon size={10} /> {s.label}
              </div>
              <div className="text-xl font-mono font-bold mt-1">{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {!stats?.built && (
        <div className="bg-card/60 border border-border/50 p-8 text-center">
          <Network size={32} className="text-muted-foreground mx-auto mb-3" />
          <p className="text-sm text-muted-foreground font-mono">Knowledge graph not built yet.</p>
          <Button onClick={handleBuild} className="mt-3 font-mono text-xs rounded-none">Build Now</Button>
        </div>
      )}

      {stats?.built && (
        <>
          {/* Tabs + Search */}
          <div className="flex flex-col md:flex-row gap-3 items-start md:items-center">
            <div className="flex gap-1">
              {["actors", "locations"].map(tab => (
                <button
                  key={tab}
                  data-testid={`tab-${tab}`}
                  onClick={() => setActiveTab(tab)}
                  className={`px-3 py-1.5 text-xs font-mono uppercase tracking-wider transition-colors ${
                    activeTab === tab ? "bg-primary text-primary-foreground" : "bg-muted/30 text-muted-foreground hover:bg-muted/50"
                  }`}
                >
                  {tab === "actors" ? <Users size={12} className="inline mr-1" /> : <MapPin size={12} className="inline mr-1" />}
                  {tab}
                </button>
              ))}
            </div>
            <form className="flex-1 max-w-sm" onSubmit={e => e.preventDefault()}>
              <div className="relative">
                <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input
                  data-testid="kg-search"
                  placeholder={`Search ${activeTab}...`}
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="pl-8 h-8 text-xs font-mono rounded-none"
                />
              </div>
            </form>
            {activeTab === "actors" && (
              <label className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono cursor-pointer">
                <input
                  type="checkbox"
                  checked={crossBorderOnly}
                  onChange={e => setCrossBorderOnly(e.target.checked)}
                  className="rounded-none"
                />
                Cross-border only
              </label>
            )}
            {activeTab === "locations" && (
              <label className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono cursor-pointer">
                <input
                  type="checkbox"
                  checked={borderOnly}
                  onChange={e => setBorderOnly(e.target.checked)}
                  className="rounded-none"
                />
                Border zones only
              </label>
            )}
          </div>

          {/* Content */}
          {activeTab === "actors" && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="actors-grid">
              {filteredActors.map(actor => (
                <ActorCard key={actor.name} actor={actor} onSelect={fetchActorDetail} />
              ))}
              {filteredActors.length === 0 && (
                <p className="text-xs text-muted-foreground font-mono col-span-3 text-center py-8">No actors found.</p>
              )}
            </div>
          )}
          {activeTab === "locations" && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="locations-grid">
              {filteredLocations.map(loc => (
                <LocationCard key={loc.name} location={loc} />
              ))}
              {filteredLocations.length === 0 && (
                <p className="text-xs text-muted-foreground font-mono col-span-3 text-center py-8">No locations found.</p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
