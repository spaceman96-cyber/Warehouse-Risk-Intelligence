// App.jsx (or WRIDashboard.jsx)
// Full working version wired to your FastAPI backend via ./api.js
// - Uses LIVE data for SKUs / Zones / Users / Recs / Spikes / Investigations
// - "Run Engine" refreshes all
// - Investigations: create + status update hits API
// - No hooks outside components

import { useState, useEffect, useMemo } from "react";
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell
} from "recharts";
import { api } from "./api";

// ─────────────────────────────────────────────────────────────
// MAPPERS (backend -> UI model)
// ─────────────────────────────────────────────────────────────
function mapSkuRow(r) {
  return {
    sku:   r.sku_code ?? r.sku ?? "",
    name:  r.sku_name ?? r.name ?? r.description ?? r.sku_code ?? "",
    cat:   r.category ?? r.cat ?? "Unknown",
    score: Number(r.risk_score ?? r.score ?? 0),
    freq:  Number(r.freq_30d ?? r.freq ?? r.adjustment_count_30d ?? r.adjustment_count ?? 0),
    drift: Number(r.drift_ratio_7d ?? r.drift ?? r.drift_ratio ?? r.drift_30d ?? 1.0),
    value: Number(r.value_at_risk ?? r.value ?? r.value_at_risk_usd ?? 0),
    zone:  r.zone ?? r.primary_zone ?? "—",
    abc:   r.abc_class ?? r.abc ?? "C",
  };
}

function mapZoneRow(z) {
  return {
    zone: z.zone ?? z.zone_code ?? "—",
    score: Number(z.risk_score ?? z.score ?? 0),
    count: Number(z.adj_count_30d ?? z.adjustment_count ?? z.count ?? 0),
    negRatio: Number(z.neg_ratio ?? z.negative_ratio ?? z.negRatio ?? 0),
  };
}

function mapUserRow(u) {
  return {
    user: u.user_ref ?? u.user ?? "—",
    score: Number(u.risk_score ?? u.score ?? 0),
    count: Number(u.adjustment_count ?? u.count ?? 0),
    negRatio: Number(u.neg_ratio ?? u.negative_ratio ?? u.negRatio ?? 0),
    endshift: Number(u.end_shift_ratio ?? u.endshift ?? 0),
  };
}

function mapRecRow(r) {
  return {
    priority: Number(r.priority ?? 999),
    sku: r.sku_code ?? r.sku ?? "",
    name: r.sku_name ?? r.name ?? r.sku_code ?? "",
    score: Number(r.risk_score ?? r.score ?? 0),
    reason: r.reason ?? r.rationale ?? "",
  };
}

// ─────────────────────────────────────────────────────────────
// THEME VARS + HELPERS
// ─────────────────────────────────────────────────────────────
const THEME_VARS = {
  dark: {
    "--bg":           "#0E0F11",
    "--bg2":          "#141517",
    "--surface":      "#1A1B1E",
    "--surface-hov":  "#1F2023",
    "--surface-pop":  "#242528",
    "--border":       "rgba(255,255,255,0.07)",
    "--border-hov":   "rgba(255,255,255,0.14)",
    "--text":         "#EDEDED",
    "--text-sub":     "#9B9BA4",
    "--text-muted":   "#5A5A65",
    "--accent":       "#F59E0B",
    "--accent-soft":  "rgba(245,158,11,0.10)",
    "--accent-glow":  "rgba(245,158,11,0.20)",
    "--red":          "#F87171",
    "--red-soft":     "rgba(248,113,113,0.10)",
    "--green":        "#4ADE80",
    "--green-soft":   "rgba(74,222,128,0.10)",
    "--blue":         "#60A5FA",
    "--blue-soft":    "rgba(96,165,250,0.10)",
    "--shadow":       "0 1px 2px rgba(0,0,0,0.45), 0 4px 16px rgba(0,0,0,0.3)",
    "--shadow-hov":   "0 2px 6px rgba(0,0,0,0.55), 0 8px 28px rgba(0,0,0,0.4)",
    "--shadow-pop":   "0 0 0 1px rgba(255,255,255,0.07), 0 8px 32px rgba(0,0,0,0.45)",
  },
  light: {
    "--bg":           "#F5F5F7",
    "--bg2":          "#EAEAEC",
    "--surface":      "#FFFFFF",
    "--surface-hov":  "#FAFAFA",
    "--surface-pop":  "#F4F4F6",
    "--border":       "rgba(0,0,0,0.07)",
    "--border-hov":   "rgba(0,0,0,0.14)",
    "--text":         "#111111",
    "--text-sub":     "#55555F",
    "--text-muted":   "#9898A2",
    "--accent":       "#D97706",
    "--accent-soft":  "rgba(217,119,6,0.09)",
    "--accent-glow":  "rgba(217,119,6,0.18)",
    "--red":          "#DC2626",
    "--red-soft":     "rgba(220,38,38,0.08)",
    "--green":        "#16A34A",
    "--green-soft":   "rgba(22,163,74,0.09)",
    "--blue":         "#2563EB",
    "--blue-soft":    "rgba(37,99,235,0.09)",
    "--shadow":       "0 1px 2px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.07)",
    "--shadow-hov":   "0 2px 6px rgba(0,0,0,0.08), 0 8px 24px rgba(0,0,0,0.10)",
    "--shadow-pop":   "0 0 0 1px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.12)",
  }
};

function applyTheme(mode) {
  const vars = THEME_VARS[mode];
  const root = document.documentElement;
  Object.entries(vars).forEach(([k,v]) => root.style.setProperty(k,v));
}

const C = {
  bg:          "var(--bg)",
  bg2:         "var(--bg2)",
  surface:     "var(--surface)",
  surfaceHov:  "var(--surface-hov)",
  surfacePop:  "var(--surface-pop)",
  border:      "var(--border)",
  borderHov:   "var(--border-hov)",
  text:        "var(--text)",
  textSub:     "var(--text-sub)",
  textMuted:   "var(--text-muted)",
  accent:      "var(--accent)",
  accentSoft:  "var(--accent-soft)",
  accentGlow:  "var(--accent-glow)",
  red:         "var(--red)",
  redSoft:     "var(--red-soft)",
  green:       "var(--green)",
  greenSoft:   "var(--green-soft)",
  blue:        "var(--blue)",
  blueSoft:    "var(--blue-soft)",
  shadow:      "var(--shadow)",
  shadowHov:   "var(--shadow-hov)",
  shadowPop:   "var(--shadow-pop)",
};

const scoreColor = s => s>=70?C.red:s>=50?C.accent:s>=30?C.blue:C.green;
const scoreSoft  = s => s>=70?C.redSoft:s>=50?C.accentSoft:s>=30?C.blueSoft:C.greenSoft;
const riskLabel  = s => s>=70?"Critical":s>=50?"High":s>=30?"Medium":"Low";
const zoneColor  = s => s>=80?C.red:s>=50?C.accent:s>=20?C.blue:C.green;
const zoneSoft   = s => s>=80?C.redSoft:s>=50?C.accentSoft:s>=20?C.blueSoft:C.greenSoft;

// ─────────────────────────────────────────────────────────────
// UI ATOMS
// ─────────────────────────────────────────────────────────────
function HoverCard({children, style={}, noPad=false, onClick}) {
  const [hov,setHov] = useState(false);
  return (
    <div
      onMouseEnter={()=>setHov(true)}
      onMouseLeave={()=>setHov(false)}
      onClick={onClick}
      style={{
        background: C.surface,
        border: `1px solid ${hov ? C.borderHov : C.border}`,
        borderRadius: 12,
        boxShadow: hov ? C.shadowHov : C.shadow,
        padding: noPad ? 0 : 20,
        overflow: "hidden",
        position: "relative",
        cursor: onClick ? "pointer" : "default",
        transform: hov && onClick ? "translateY(-1px)" : "translateY(0)",
        ...style,
      }}
    >{children}</div>
  );
}

function ScoreRing({score, size=44}) {
  const [anim,setAnim] = useState(0);
  useEffect(()=>{const t=setTimeout(()=>setAnim(score),80);return()=>clearTimeout(t)},[score]);
  const r=(size/2)-5, circ=2*Math.PI*r, dash=(anim/100)*circ;
  const c = scoreColor(score);
  return (
    <svg width={size} height={size} style={{transform:"rotate(-90deg)",flexShrink:0}}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={C.border} strokeWidth={2.5}/>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={c} strokeWidth={2.5}
        strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
        style={{transition:"stroke-dasharray 1.1s cubic-bezier(0.16,1,0.3,1)"}}/>
      <text x={size/2} y={size/2+1} textAnchor="middle" dominantBaseline="middle"
        fill={c} fontSize={size>40?11:9} fontWeight={700} fontFamily="monospace"
        style={{transform:"rotate(90deg)",transformOrigin:`${size/2}px ${size/2}px`}}>
        {score}
      </text>
    </svg>
  );
}

const Chip = ({label, color, bg}) => (
  <span className="chip" style={{color,background:bg,border:`1px solid ${color}28`}}>{label}</span>
);
const RiskChip = ({score}) => <Chip label={riskLabel(score)} color={scoreColor(score)} bg={scoreSoft(score)}/>;

function AnimBar({value, color, width=68}) {
  const [w,setW]=useState(0);
  useEffect(()=>{const t=setTimeout(()=>setW(value),100);return()=>clearTimeout(t)},[value]);
  return (
    <div style={{display:"flex",alignItems:"center",gap:7}}>
      <div className="bar-track" style={{width}}>
        <div className="bar-fill" style={{width:`${w*100}%`,background:color}}/>
      </div>
      <span style={{fontFamily:"monospace",fontSize:10,color,minWidth:30}}>{(value*100).toFixed(0)}%</span>
    </div>
  );
}

function ScoreBar({score, width=60}) {
  const [w,setW]=useState(0);
  useEffect(()=>{const t=setTimeout(()=>setW(score),100);return()=>clearTimeout(t)},[score]);
  const c=scoreColor(score);
  return (
    <div style={{display:"flex",alignItems:"center",gap:8}}>
      <div className="bar-track" style={{width}}>
        <div className="bar-fill" style={{width:`${w}%`,background:c}}/>
      </div>
      <span style={{fontFamily:"monospace",fontSize:12,fontWeight:700,color:c,minWidth:22}}>{score}</span>
    </div>
  );
}

function TR({children}) {
  const [h,setH] = useState(false);
  return (
    <tr onMouseEnter={()=>setH(true)} onMouseLeave={()=>setH(false)}
      style={{background:h?C.surfacePop:"transparent",cursor:"pointer"}}>
      {children}
    </tr>
  );
}

function RowHover({children, style={}}) {
  const [h,setH] = useState(false);
  return (
    <div onMouseEnter={()=>setH(true)} onMouseLeave={()=>setH(false)}
      style={{...style,background:h?C.surfacePop:"transparent",cursor:"pointer",borderRadius:8}}>
      {children}
    </div>
  );
}

const ChartTip = ({active,payload,label}) => {
  if(!active||!payload?.length) return null;
  return (
    <div style={{background:C.surfacePop,border:`1px solid ${C.borderHov}`,
      borderRadius:8,padding:"8px 12px",boxShadow:C.shadowPop}}>
      <div style={{fontSize:10,color:C.textMuted,marginBottom:3,fontFamily:"monospace"}}>Day {label}</div>
      <div style={{fontFamily:"monospace",fontSize:13,fontWeight:700,color:C.accent}}>{payload[0]?.value} adj</div>
    </div>
  );
};

function AlertBanner({icon,text,action}) {
  return (
    <div style={{background:C.redSoft,border:`1px solid var(--red-border)`,
      borderRadius:10,padding:"11px 16px",display:"flex",alignItems:"center",gap:12}}>
      <span style={{fontSize:15,flexShrink:0}}>{icon}</span>
      <span style={{fontSize:12,color:C.red,fontWeight:500,flex:1,lineHeight:1.5}}>{text}</span>
      {action && <button className="btn-outline-red">{action}</button>}
    </div>
  );
}

const CardHead = ({title,sub,right,noBorder=false}) => (
  <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",
    marginBottom: noBorder?16:0,
    padding: noBorder?"0":"14px 18px",
    borderBottom: noBorder?"none":`1px solid ${C.border}`}}>
    <div>
      <div style={{fontSize:13,fontWeight:600,color:C.text,letterSpacing:-0.1}}>{title}</div>
      {sub && <div style={{fontSize:11,color:C.textMuted,marginTop:1}}>{sub}</div>}
    </div>
    {right && <div>{right}</div>}
  </div>
);

function BtnPrimary({label,onClick,disabled=false}) {
  const [h,setH]=useState(false);
  return (
    <button onClick={onClick} disabled={disabled}
      onMouseEnter={()=>setH(true)} onMouseLeave={()=>setH(false)}
      style={{
        fontSize:11,fontWeight:600,padding:"6px 14px",borderRadius:8,cursor:disabled?"not-allowed":"pointer",
        background:C.accent,color:"#000",border:"none",
        opacity:disabled?0.5:(h?0.82:1),
        boxShadow:`0 2px 10px ${C.accentGlow}`
      }}>
      {label}
    </button>
  );
}

function BtnGhost({label,onClick}) {
  const [h,setH]=useState(false);
  return (
    <button onClick={onClick}
      onMouseEnter={()=>setH(true)} onMouseLeave={()=>setH(false)}
      style={{fontSize:11,fontWeight:500,padding:"6px 12px",borderRadius:8,cursor:"pointer",
        background:h?C.surfacePop:"transparent",color:C.textSub,
        border:`1px solid ${h?C.borderHov:C.border}`}}>
      {label}
    </button>
  );
}

function NavItem({children,active,onClick}) {
  const [h,setH]=useState(false);
  return (
    <div onClick={onClick}
      onMouseEnter={()=>setH(true)} onMouseLeave={()=>setH(false)}
      style={{display:"flex",alignItems:"center",gap:8,padding:"7px 10px",cursor:"pointer",
        margin:"1px 8px",borderRadius:8,
        background:active?C.accentSoft:h?C.surfacePop:"transparent",
        color:active?C.accent:h?C.text:C.textSub,
        fontWeight:active?600:400,fontSize:13}}>
      {children}
    </div>
  );
}


function UploadDataCard({ onUploadSku, onUploadAdj, uploading, message, error }) {
  const [drag, setDrag] = useState(false);

  const onDrop = async (e) => {
    e.preventDefault();
    setDrag(false);

    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) return;

    // Simple heuristic:
    // if filename contains "sku" -> SKU master; else treat as adjustments
    const isSku = file.name.toLowerCase().includes("sku");
    if (isSku) await onUploadSku(file);
    else await onUploadAdj(file);
  };

  const pickFile = (accept, cb) => {
    const inp = document.createElement("input");
    inp.type = "file";
    inp.accept = accept;
    inp.onchange = () => {
      const f = inp.files?.[0];
      if (f) cb(f);
    };
    inp.click();
  };

  return (
    <HoverCard>
      <CardHead
        noBorder
        title="Upload Data"
        sub="Upload CSVs → backend saves to DB → dashboard refreshes"
        right={uploading ? <span className="badge-accent">Uploading…</span> : <span className="badge-accent">CSV</span>}
      />

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        style={{
          border: `1px dashed ${drag ? C.accent : C.border}`,
          background: drag ? C.accentSoft : C.bg2,
          borderRadius: 12,
          padding: "14px 14px",
          marginTop: 10,
        }}
      >
        <div style={{ fontSize: 12, color: C.textSub, lineHeight: 1.6 }}>
          <div style={{ fontWeight: 700, color: C.text, marginBottom: 4 }}>
            Drag & drop a CSV here
          </div>
          <div style={{ color: C.textMuted }}>
            If filename contains <span style={{ fontFamily: "monospace" }}>sku</span> → SKU Master. Otherwise → Adjustments.
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
        <button
          className="btn-primary"
          disabled={uploading}
          onClick={() => pickFile(".csv", onUploadSku)}
          title="Upload SKU master CSV"
        >
          Upload SKU Master
        </button>

        <button
          className="btn-ghost-active"
          disabled={uploading}
          onClick={() => pickFile(".csv", onUploadAdj)}
          title="Upload adjustments CSV"
        >
          Upload Adjustments
        </button>

        <div style={{ flex: 1 }} />
      </div>

      {(message || error) && (
        <div
          style={{
            marginTop: 12,
            padding: "10px 12px",
            borderRadius: 10,
            border: `1px solid ${error ? "rgba(248,113,113,0.28)" : C.border}`,
            background: error ? C.redSoft : C.surfacePop,
            color: error ? C.red : C.textSub,
            fontSize: 11,
            lineHeight: 1.6,
            whiteSpace: "pre-wrap",
            fontFamily: "monospace",
          }}
        >
          {error ? `ERROR: ${error}` : message}
        </div>
      )}

      <div style={{ marginTop: 10, fontSize: 10, color: C.textMuted, lineHeight: 1.5 }}>
        Tip: Upload SKU master first, then adjustments. Re-uploading adjustments won’t double-insert after we add dedupe.
      </div>
    </HoverCard>
  );
}
// ─────────────────────────────────────────────────────────────
// VIEWS (LIVE DATA)
// ─────────────────────────────────────────────────────────────
function Overview({ skuData, zones, spikes, cases, trend }) {
  const highRisk = skuData.filter(s=>s.score>=60).length;
  const totalVal = skuData.reduce((a,b)=>a + (Number(b.value)||0), 0);

  const activeCases = (cases || []).filter(c => c.status !== "closed").length;

  const kpis=[
    {label:"High-Risk SKUs", value:String(highRisk),                         color:C.red,   soft:C.redSoft,   icon:"⚠"},
    {label:"Value at Risk",  value:`$${(totalVal/1000).toFixed(1)}K`,        color:C.accent,soft:C.accentSoft,icon:"◈"},
    {label:"Spike Alerts",   value:String(spikes?.length || 0),              color:C.blue,  soft:C.blueSoft,  icon:"↑"},
    {label:"Open Cases",     value:String(activeCases),                     color:C.green, soft:C.greenSoft, icon:"◷"},
  ];
  const sub=["Score ≥ 60","30-day exposure","Immediate review","Active investigations"];

  const topRisk = [...skuData].sort((a,b)=>b.score-a.score).slice(0,5);

  // If you don't have real trend endpoint yet, we use provided `trend` prop.
  const trendData = trend || [];

  return (
    <div className="col" style={{gap:16}}>

      {(spikes?.length || 0) > 0 ? (
        <AlertBanner icon="⚡"
          text={<><b>Spike Detected</b> — {spikes[0]?.sku_code || spikes[0]?.sku || "SKU"} rate above baseline.</>}
          action="Open Case →"/>
      ) : (
        <AlertBanner icon="✅"
          text={<><b>No spikes</b> — no SKU exceeded the spike threshold in the last 7 days.</>}
        />
      )}

      <div className="grid-4" style={{gap:12}}>
        {kpis.map((k,i)=>(
          <HoverCard key={k.label}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
              <div>
                <div style={{fontSize:11,color:C.textMuted,fontWeight:500,marginBottom:10}}>{k.label}</div>
                <div style={{fontSize:30,fontWeight:800,color:k.color,letterSpacing:-1,lineHeight:1}}>{k.value}</div>
                <div style={{fontSize:11,color:C.textMuted,marginTop:7}}>{sub[i]}</div>
              </div>
              <div style={{width:33,height:33,borderRadius:9,background:k.soft,
                display:"flex",alignItems:"center",justifyContent:"center",
                fontSize:14,color:k.color,fontFamily:"monospace",fontWeight:700}}>{k.icon}</div>
            </div>
            <div style={{position:"absolute",bottom:0,left:0,right:0,height:1,
              background:`linear-gradient(90deg,${k.color}45,transparent)`}}/>
          </HoverCard>
        ))}
      </div>

      <div className="grid-65" style={{gap:16}}>
        <HoverCard>
          <CardHead noBorder title="Adjustment Trend" sub="Last 30 days"
            right={<span className="badge-accent">Live</span>}/>
          <ResponsiveContainer width="100%" height={155}>
            <AreaChart data={trendData} margin={{top:4,right:0,left:-28,bottom:0}}>
              <defs>
                <linearGradient id="ga" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor="var(--accent)" stopOpacity={0.22}/>
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" vertical={false}/>
              <XAxis dataKey="d" tick={{fill:"var(--text-muted)",fontSize:9,fontFamily:"monospace"}} interval={4} axisLine={false} tickLine={false}/>
              <YAxis tick={{fill:"var(--text-muted)",fontSize:9,fontFamily:"monospace"}} axisLine={false} tickLine={false}/>
              <Tooltip content={<ChartTip/>}/>
              <Area type="monotone" dataKey="adj" stroke="var(--accent)" strokeWidth={2}
                fill="url(#ga)" dot={false} activeDot={{r:4,fill:"var(--accent)",strokeWidth:0}}/>
            </AreaChart>
          </ResponsiveContainer>
        </HoverCard>

        <HoverCard>
          <CardHead noBorder title="Zone Risk" sub="Sorted highest → lowest"/>
          <div className="col" style={{gap:12}}>
            {zones.map(z=>(
              <div key={z.zone} style={{display:"flex",alignItems:"center",gap:10}}>
                <div style={{width:32,height:32,borderRadius:8,flexShrink:0,
                  background:zoneSoft(z.score),border:`1px solid ${zoneColor(z.score)}28`,
                  display:"flex",alignItems:"center",justifyContent:"center",
                  fontFamily:"monospace",fontSize:13,fontWeight:700,color:zoneColor(z.score)}}>
                  {z.zone}
                </div>
                <div style={{flex:1}}>
                  <div className="bar-track" style={{marginBottom:3}}>
                    <div className="bar-fill" style={{width:`${z.score}%`,background:zoneColor(z.score),
                      transition:"width 1.1s cubic-bezier(0.16,1,0.3,1)"}}/>
                  </div>
                  <div style={{fontSize:10,color:C.textMuted,fontFamily:"monospace"}}>
                    {z.count} adj · {(z.negRatio*100).toFixed(0)}% neg
                  </div>
                </div>
                <span style={{fontFamily:"monospace",fontSize:12,fontWeight:700,
                  color:zoneColor(z.score),minWidth:24,textAlign:"right"}}>{z.score}</span>
              </div>
            ))}
          </div>
        </HoverCard>
      </div>

      <div className="grid-2" style={{gap:16}}>
      
        <HoverCard>
          <CardHead noBorder title="Top Risk SKUs" sub="Highest scores right now"/>
          <div className="col" style={{gap:10}}>
            {topRisk.map(s=>(
              <RowHover key={s.sku} style={{display:"flex",alignItems:"center",gap:10,padding:"4px 6px",margin:"0 -6px"}}>
                <ScoreRing score={s.score} size={36}/>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{fontSize:12,fontWeight:500,color:C.text,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{s.name}</div>
                  <div style={{fontSize:10,color:C.textMuted,fontFamily:"monospace"}}>{s.cat} · Zone {s.zone}</div>
                </div>
                <RiskChip score={s.score}/>
              </RowHover>
            ))}
          </div>
        </HoverCard>
      </div>

      {/* Fix: Category bar Cells (render after chart so we have data) */}
      <style>{``}</style>
    </div>
  );
}

function CategoryRisk({ skuData }) {
  const cats = useMemo(() => {
    const by = new Map();
    for (const s of skuData) {
      const k = s.cat || "Unknown";
      const cur = by.get(k) || { cat: k, sum: 0, n: 0 };
      cur.sum += Number(s.score) || 0;
      cur.n += 1;
      by.set(k, cur);
    }
    return Array.from(by.values())
      .map(x => ({ cat: x.cat, avg: x.n ? Math.round(x.sum/x.n) : 0 }))
      .sort((a,b)=>b.avg-a.avg);
  }, [skuData]);

  return (
    <HoverCard>
      <CardHead noBorder title="Category Risk" sub="Average composite score"/>
      <ResponsiveContainer width="100%" height={130}>
        <BarChart data={cats} margin={{top:0,right:0,left:-28,bottom:0}} barSize={30}>
          <CartesianGrid strokeDasharray="4 4" stroke="var(--border)" vertical={false}/>
          <XAxis dataKey="cat" tick={{fill:"var(--text-muted)",fontSize:9,fontFamily:"monospace"}} axisLine={false} tickLine={false}/>
          <YAxis tick={{fill:"var(--text-muted)",fontSize:9,fontFamily:"monospace"}} domain={[0,100]} axisLine={false} tickLine={false}/>
          <Tooltip content={<ChartTip/>}/>
          <Bar dataKey="avg" radius={[4,4,0,0]}>
            {cats.map((c,i)=><Cell key={i} fill={scoreColor(c.avg)} fillOpacity={0.9}/>)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </HoverCard>
  );
}

function SKUView({ skuData, zones, scoreDate }) {
  const [cat,setCat]=useState("All");
  const cats=["All","Beverages","Frozen","Personal Care","Household","Snacks","Unknown"];
  const data = cat==="All" ? skuData : skuData.filter(s=>s.cat===cat);

  const th={fontSize:10,fontWeight:600,color:C.textMuted,textAlign:"left",
    padding:"10px 16px",whiteSpace:"nowrap",borderBottom:`1px solid ${C.border}`};
  const td={padding:"11px 16px",borderBottom:`1px solid ${C.border}`,verticalAlign:"middle"};

  return (
    <HoverCard noPad>
      <div style={{padding:"14px 18px",borderBottom:`1px solid ${C.border}`,
        display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:10}}>
        <div>
          <div style={{fontSize:13,fontWeight:600,color:C.text}}>SKU Risk Scores</div>
          <div style={{fontSize:11,color:C.textMuted,marginTop:1}}>{data.length} SKUs · {scoreDate}</div>
        </div>
        <div style={{display:"flex",gap:4,flexWrap:"wrap"}}>
          {cats.map(c=>(
            <button key={c} onClick={()=>setCat(c)} className={`filter-btn ${cat===c?"active":""}`}>{c}</button>
          ))}
        </div>
      </div>

      <div style={{overflowX:"auto"}}>
        <table style={{width:"100%",borderCollapse:"collapse"}}>
          <thead>
            <tr style={{background:C.bg2}}>
              {["SKU","Name","Category","Zone","Freq 30d","Drift","$ Risk","ABC","Score","Level"].map(h=>(
                <th key={h} style={th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map(s=>(
              <TR key={s.sku}>
                <td style={td}><span style={{fontFamily:"monospace",fontSize:11,fontWeight:700,color:C.accent}}>{s.sku}</span></td>
                <td style={{...td,fontSize:13,fontWeight:500,color:C.text}}>{s.name}</td>
                <td style={{...td,fontSize:11,color:C.textSub}}>{s.cat}</td>
                <td style={td}>
                  <span style={{fontFamily:"monospace",fontSize:12,fontWeight:700,
                    color:zoneColor(zones.find(z=>z.zone===s.zone)?.score||0)}}>{s.zone}</span>
                </td>
                <td style={td}>
                  <div style={{display:"flex",alignItems:"center",gap:6}}>
                    <div className="bar-track" style={{width:46}}>
                      <div className="bar-fill" style={{width:`${Math.min(100,(s.freq/20)*100)}%`,background:C.blue}}/>
                    </div>
                    <span style={{fontFamily:"monospace",fontSize:10,color:C.textSub}}>{s.freq}</span>
                  </div>
                </td>
                <td style={td}>
                  <span style={{fontFamily:"monospace",fontSize:11,fontWeight:600,
                    color:s.drift>1.5?C.red:s.drift>1.1?C.accent:C.green}}>
                    {s.drift>1.5?"↑↑":s.drift>1.1?"↑":"→"} {Number(s.drift).toFixed(2)}×
                  </span>
                </td>
                <td style={td}>
                  <span style={{fontFamily:"monospace",fontSize:12,fontWeight:600,
                    color:s.value>500?C.red:C.accent}}>${Number(s.value||0).toLocaleString()}</span>
                </td>
                <td style={td}>
                  <Chip label={s.abc}
                    color={s.abc==="A"?C.accent:s.abc==="B"?C.blue:C.textMuted}
                    bg={s.abc==="A"?C.accentSoft:s.abc==="B"?C.blueSoft:"transparent"}/>
                </td>
                <td style={td}><ScoreBar score={s.score} width={54}/></td>
                <td style={td}><RiskChip score={s.score}/></td>
              </TR>
            ))}
          </tbody>
        </table>
      </div>
    </HoverCard>
  );
}

function RecsView({ recs }) {
  return (
    <div className="col" style={{gap:16}}>
      <HoverCard noPad>
        <CardHead title="Cycle Count Recommendations"
          sub={`Count these ${recs.length} SKUs tomorrow · Ranked by risk`}
          right={<BtnPrimary label="Export List" onClick={()=>{ /* later */ }}/>} />
        <div style={{padding:"4px 16px"}}>
          {recs.map((r,i)=>(
            <RowHover key={`${r.sku}-${r.priority}`}
              style={{display:"flex",alignItems:"center",gap:14,padding:"11px 4px",
                margin:"0 -4px",borderBottom:i<recs.length-1?`1px solid ${C.border}`:"none"}}>
              <div style={{width:30,height:30,borderRadius:8,flexShrink:0,
                background:r.priority<=2?C.accentSoft:C.border,
                display:"flex",alignItems:"center",justifyContent:"center",
                fontFamily:"monospace",fontSize:12,fontWeight:700,
                color:r.priority<=2?C.accent:C.textMuted}}>#{r.priority}</div>
              <ScoreRing score={r.score} size={40}/>
              <div style={{flex:1,minWidth:0}}>
                <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:2,flexWrap:"wrap"}}>
                  <span style={{fontFamily:"monospace",fontSize:11,fontWeight:700,color:C.accent}}>{r.sku}</span>
                  <span style={{fontSize:13,fontWeight:500,color:C.text}}>{r.name}</span>
                </div>
                <div style={{fontSize:11,color:C.textMuted}}>{r.reason}</div>
              </div>
              <RiskChip score={r.score}/>
            </RowHover>
          ))}
        </div>
      </HoverCard>
    </div>
  );
}

function UsersView({ users }) {
  const th={fontSize:10,fontWeight:600,color:C.textMuted,textAlign:"left",
    padding:"10px 16px",borderBottom:`1px solid ${C.border}`,whiteSpace:"nowrap"};
  const td={padding:"12px 16px",borderBottom:`1px solid ${C.border}`,verticalAlign:"middle"};

  const top = users[0];

  return (
    <div className="col" style={{gap:16}}>
      {top && top.score >= 60 ? (
        <AlertBanner icon="👤"
          text={<><b>{top.user} flagged</b> — {(top.negRatio*100).toFixed(0)}% negative · {(top.endshift*100).toFixed(0)}% end-of-shift · Score: {top.score}/100</>}
          action="Investigate"/>
      ) : (
        <AlertBanner icon="✅"
          text={<><b>No high-risk users</b> — no user exceeded your anomaly threshold.</>}
        />
      )}

      <HoverCard noPad>
        <CardHead title="User Anomaly Scores" sub="Last 30 days · Sorted by risk"/>
        <table style={{width:"100%",borderCollapse:"collapse"}}>
          <thead><tr style={{background:C.bg2}}>
            {["User","Adj Count","Negative Ratio","End-Shift %","Anomaly Score","Action"].map(h=>(
              <th key={h} style={th}>{h}</th>
            ))}
          </tr></thead>
          <tbody>
            {users.map(u=>(
              <TR key={u.user}>
                <td style={td}>
                  <div style={{display:"flex",alignItems:"center",gap:9}}>
                    <div style={{width:28,height:28,borderRadius:8,flexShrink:0,
                      background:u.score>=60?C.redSoft:C.blueSoft,
                      display:"flex",alignItems:"center",justifyContent:"center",
                      fontFamily:"monospace",fontSize:10,fontWeight:700,
                      color:u.score>=60?C.red:C.blue}}>
                      {(u.user || "—").split("-")[1] || "•"}
                    </div>
                    <span style={{fontSize:12,fontWeight:600,color:u.score>=60?C.red:C.text}}>{u.user}</span>
                  </div>
                </td>
                <td style={{...td,fontFamily:"monospace",fontSize:12,color:C.textSub}}>{u.count}</td>
                <td style={td}><AnimBar value={u.negRatio} color={u.negRatio>0.7?C.red:C.blue}/></td>
                <td style={td}><AnimBar value={u.endshift} color={u.endshift>0.6?C.accent:C.textMuted}/></td>
                <td style={td}><ScoreBar score={u.score} width={80}/></td>
                <td style={td}>
                  {u.score>=60
                    ?<button className="btn-investigate">Investigate</button>
                    :u.score>=30
                    ?<Chip label="Monitor" color={C.accent} bg={C.accentSoft}/>
                    :<Chip label="Clear"   color={C.green}  bg={C.greenSoft}/>}
                </td>
              </TR>
            ))}
          </tbody>
        </table>
      </HoverCard>
    </div>
  );
}

function InvestigationsView({ cases, setCases }) {
  const [show,setShow]=useState(false);
  const [form,setForm]=useState({title:"",sev:"med",owner:""});

  const submit = async () => {
    if (!form.title.trim()) return;
    const created = await api.investigationsCreate({
      title: form.title,
      severity: form.sev,
      owner: form.owner || null,
    });
    setCases([created, ...(cases || [])]);
    setShow(false);
    setForm({ title: "", sev: "med", owner: "" });
  };

  const statusColor={open:C.blue,in_progress:C.accent,blocked:C.red,closed:C.green};
  const sevColor={high:C.red,med:C.accent,low:C.green};

  const normalize = (c) => ({
    id: c.id,
    title: c.title,
    status: c.status,
    sev: c.severity ?? c.sev ?? "med",
    owner: c.owner ?? null,
    opened: (c.opened_at || c.opened || "").slice(0,10) || "—",
    sku: c.links?.find(l=>l.type==="sku")?.key || c.sku || null,
  });

  const list = (cases || []).map(normalize);

  return (
    <div className="col" style={{gap:14}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
        <div style={{fontSize:13,fontWeight:600,color:C.text}}>
          {list.length} Cases · <span style={{color:C.textMuted,fontWeight:400}}>{list.filter(c=>c.status!=="closed").length} active</span>
        </div>
        <button onClick={()=>setShow(!show)} className={show?"btn-ghost-active":"btn-primary"}>
          {show?"Cancel":"+ Open Case"}
        </button>
      </div>

      {show && (
        <HoverCard>
          <div style={{fontSize:13,fontWeight:600,color:C.text,marginBottom:14}}>New Investigation</div>
          <div className="grid-2" style={{gap:12}}>
            <div style={{gridColumn:"1/-1"}}>
              <div className="form-label">Case Title</div>
              <input value={form.title} onChange={e=>setForm({...form,title:e.target.value})}
                placeholder="e.g. SKU-007 chronic variance" className="form-input"/>
            </div>
            <div>
              <div className="form-label">Severity</div>
              <select value={form.sev} onChange={e=>setForm({...form,sev:e.target.value})} className="form-input">
                <option value="low">Low</option><option value="med">Medium</option><option value="high">High</option>
              </select>
            </div>
            <div>
              <div className="form-label">Assigned To</div>
              <input value={form.owner} onChange={e=>setForm({...form,owner:e.target.value})}
                placeholder="Name or user ID" className="form-input"/>
            </div>
          </div>
          <button onClick={submit} className="btn-primary" style={{marginTop:14}}>Open Investigation</button>
        </HoverCard>
      )}

      {list.map(c=>(
        <HoverCard key={c.id} onClick={()=>{}}>
          <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",gap:12,marginBottom:12}}>
            <div style={{flex:1}}>
              <div style={{fontSize:14,fontWeight:600,color:C.text,marginBottom:5,letterSpacing:-0.1}}>{c.title}</div>
              <div style={{display:"flex",gap:10,fontSize:11,color:C.textMuted,flexWrap:"wrap"}}>
                <span>Opened {c.opened}</span>
                {c.owner && <span>→ {c.owner}</span>}
                {c.sku && <span style={{color:C.accent,fontFamily:"monospace"}}>{c.sku}</span>}
              </div>
            </div>
            <div style={{display:"flex",gap:6,flexShrink:0}}>
              <Chip label={c.sev} color={sevColor[c.sev]} bg={`${sevColor[c.sev]}12`}/>
              <Chip label={c.status.replace("_"," ")} color={statusColor[c.status]} bg={`${statusColor[c.status]}12`}/>
            </div>
          </div>

          <div style={{display:"flex",gap:5,flexWrap:"wrap"}}>
            {["open","in_progress","blocked","closed"].map(s=>(
              <button key={s}
                onClick={async e=>{
                  e.stopPropagation();
                  const updated = await api.investigationsUpdate(c.id, { status: s });
                  setCases((cases || []).map(x => x.id === c.id ? updated : x));
                }}
                className="status-btn"
                style={{
                  color:c.status===s?statusColor[s]:C.textMuted,
                  background:c.status===s?`${statusColor[s]}12`:"transparent",
                  borderColor:c.status===s?`${statusColor[s]}30`:C.border
                }}>
                {s.replace("_"," ")}
              </button>
            ))}
          </div>
        </HoverCard>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// NAV
// ─────────────────────────────────────────────────────────────
const NAV=[
  {id:"overview",icon:"⬡",label:"Overview",       section:"Monitor"},
  {id:"sku",     icon:"▤", label:"SKU Risk",       section:"Monitor"},
  {id:"recs",    icon:"✓", label:"Cycle Count",    section:"Action"},
  {id:"users",   icon:"◎", label:"User Anomaly",   section:"Action"},
  {id:"cases",   icon:"◷", label:"Investigations", section:"Cases"},
];

// ─────────────────────────────────────────────────────────────
// APP
// ─────────────────────────────────────────────────────────────
export default function App() {
  const [dark,setDark]=useState(true);
  const [view,setView]=useState("overview");

  const [skuData, setSkuData] = useState([]);
  const [zones, setZones] = useState([]);
  const [users, setUsers] = useState([]);
  const [recs, setRecs] = useState([]);
  const [spikes, setSpikes] = useState([]);
  const [scoreDate, setScoreDate] = useState("—");
  const [cases, setCases] = useState([]);

  const [loading, setLoading] = useState(false);

  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [uploadErr, setUploadErr] = useState("");
  // simple synthetic trend until you expose a trend endpoint
  const trend = useMemo(() => {
    // if you later add backend trend endpoint, replace this with API data
    const n = 30;
    const base = Math.max(6, Math.min(18, Math.round((skuData.reduce((a,b)=>a+(b.freq||0),0) / Math.max(1, skuData.length)) || 10)));
    return Array.from({length:n},(_,i)=>({
      d: `${i+1}`,
      adj: Math.max(2, Math.round(base + Math.sin(i/2.8)*3 + (i>22?6:0) + (i%4===0?2:0)))
    }));
  }, [skuData]);

const refreshAll = async () => {
  setLoading(true);
  try {
    const safe = async (p, fallback) => {
    try { return await p; }
    catch { return fallback; }
  };

  const [skuRes, zoneRes, recRes, userRes, spikeRes, invRes] = await Promise.all([
    api.skuScores({ min_score: 0 }),
    api.zoneScores({ min_score: 0 }),
    api.recommendations({ min_score: 0 }),
    safe(api.userScores({ min_score: 0 }), { results: [], score_date: null }),
    safe(api.spikes(), { results: [] }),
    safe(api.investigationsList(), { results: [] }),
  ]);

  setScoreDate(
    skuRes.score_date ||
    zoneRes.score_date ||
    recRes.rec_date ||
    "—"
  );

  setSkuData((skuRes.results || []).map(mapSkuRow));
  setZones((zoneRes.results || []).map(mapZoneRow));
  setRecs((recRes.results || []).map(mapRecRow));
  setUsers((userRes.results || []).map(mapUserRow));
  setSpikes(spikeRes.results || []);
  setCases(invRes.results || []);
  } finally {
    setLoading(false);
  }
};
  const uploadSku = async (file) => {
    setUploading(true);
    setUploadErr("");
    setUploadMsg("");
    try {
      const res = await api.uploadSkuMaster(file);
      setUploadMsg(
        `SKU MASTER SAVED ✅
file: ${res.filename || file.name}
rows: ${res.rows_ingested ?? "?"}
upserted: ${res.rows_upserted ?? res.rows_ingested ?? "?"}`
      );
      await refreshAll();
    } catch (e) {
      setUploadErr(e?.message || String(e));
    } finally {
      setUploading(false);
    }
  };

  const uploadAdj = async (file) => {
    setUploading(true);
    setUploadErr("");
    setUploadMsg("");
    try {
      const res = await api.uploadAdjustments(file);
      setUploadMsg(
        `ADJUSTMENTS SAVED ✅
file: ${res.filename || file.name}
rows_in_file: ${res.rows_ingested ?? "?"}
inserted: ${res.rows_inserted ?? "?"}
skipped(dedupe): ${res.rows_skipped ?? 0}
total_rows: ${res.total_rows ?? "?"}`
      );
      await refreshAll();
    } catch (e) {
      setUploadErr(e?.message || String(e));
    } finally {
      setUploading(false);
    }
  };
  useEffect(()=>{ applyTheme(dark?"dark":"light"); },[dark]);
  useEffect(() => { refreshAll().catch(console.error); }, []);

  const cur = NAV.find(n=>n.id===view);
  const sections = [...new Set(NAV.map(n=>n.section))];

  const renderView = () => {
    if(view==="overview") return (
      <div className="col" style={{gap:16}}>
        {/* Split CategoryRisk to keep Cells rendering clean */}
        <Overview skuData={skuData} zones={zones} spikes={spikes} cases={cases} trend={trend} />
                <div className="grid-2" style={{gap:16}}>
          <CategoryRisk skuData={skuData} />

          <UploadDataCard
            uploading={uploading}
            message={uploadMsg}
            error={uploadErr}
            onUploadSku={uploadSku}
            onUploadAdj={uploadAdj}
          />
        </div>

        <div className="grid-2" style={{gap:16, marginTop: 16}}>
          <HoverCard>
            <CardHead noBorder title="Data Status" sub="Backend connectivity"/>
            <div style={{fontSize:12,color:C.textSub,lineHeight:1.65}}>
              <div><span style={{color:C.textMuted}}>API Base:</span> <span style={{fontFamily:"monospace"}}>{import.meta.env.VITE_API_BASE || "http://localhost:8000"}</span></div>
              <div><span style={{color:C.textMuted}}>Score Date:</span> <span style={{fontFamily:"monospace"}}>{scoreDate}</span></div>
              <div><span style={{color:C.textMuted}}>SKUs:</span> <span style={{fontFamily:"monospace"}}>{skuData.length}</span></div>
              <div><span style={{color:C.textMuted}}>Zones:</span> <span style={{fontFamily:"monospace"}}>{zones.length}</span></div>
              <div><span style={{color:C.textMuted}}>Users:</span> <span style={{fontFamily:"monospace"}}>{users.length}</span></div>
            </div>
          </HoverCard>

          {/* Optional: keep this empty for layout symmetry or add another KPI card later */}
          <div />
        </div>
      </div>
    );
    if(view==="sku")   return <SKUView skuData={skuData} zones={zones} scoreDate={scoreDate} />;
    if(view==="recs")  return <RecsView recs={recs} />;
    if(view==="users") return <UsersView users={users} />;
    if(view==="cases") return <InvestigationsView cases={cases} setCases={setCases} />;
    return null;
  };

  return (
    <div style={{display:"flex",height:"100vh",background:C.bg,color:C.text,
      fontFamily:"'DM Sans','Helvetica Neue',system-ui,sans-serif",
      fontSize:14,overflow:"hidden"}}>

      {/* Sidebar */}
      <div style={{width:212,minWidth:212,background:C.surface,
        borderRight:`1px solid ${C.border}`,display:"flex",flexDirection:"column"}}>
        <div style={{padding:"17px 16px 13px",borderBottom:`1px solid ${C.border}`}}>
          <div style={{display:"flex",alignItems:"center",gap:10}}>
            <div style={{width:30,height:30,borderRadius:8,
              background:C.accent,
              display:"flex",alignItems:"center",justifyContent:"center",
              fontSize:14,fontWeight:800,color:"#000",
              boxShadow:`0 3px 10px ${C.accentGlow}`}}>W</div>
            <div>
              <div style={{fontSize:13,fontWeight:700,color:C.text,letterSpacing:-0.1}}>WRI</div>
              <div style={{fontSize:9,color:C.textMuted,letterSpacing:0.8,textTransform:"uppercase"}}>Risk Intelligence</div>
            </div>
          </div>
        </div>

        <div style={{flex:1,padding:"6px 0",overflowY:"auto"}}>
          {sections.map(sec=>(
            <div key={sec}>
              <div style={{fontSize:10,fontWeight:600,color:C.textMuted,
                padding:"10px 14px 3px",textTransform:"uppercase",letterSpacing:0.8}}>{sec}</div>
              {NAV.filter(n=>n.section===sec).map(n=>(
                <NavItem key={n.id} active={view===n.id} onClick={()=>setView(n.id)}>
                  <span style={{fontSize:12,width:16,textAlign:"center",opacity:view===n.id?1:0.5,flexShrink:0}}>{n.icon}</span>
                  <span style={{flex:1}}>{n.label}</span>
                </NavItem>
              ))}
            </div>
          ))}
        </div>

        <div style={{padding:"12px 14px",borderTop:`1px solid ${C.border}`}}>
          <div style={{display:"flex",alignItems:"center",gap:7,marginBottom:4}}>
            <div className="pulse-dot"/>
            <span style={{fontSize:11,color:C.textMuted,fontWeight:500}}>{loading ? "Refreshing…" : "Engine Active"}</span>
          </div>
          <div style={{fontSize:10,color:C.textMuted}}>SG-WH-01 · {scoreDate}</div>
        </div>
      </div>

      {/* Main */}
      <div style={{flex:1,display:"flex",flexDirection:"column",overflow:"hidden"}}>
        <div style={{background:C.surface,borderBottom:`1px solid ${C.border}`,
          padding:"12px 22px",display:"flex",alignItems:"center",
          justifyContent:"space-between",flexShrink:0}}>
          <div>
            <div style={{fontSize:15,fontWeight:700,color:C.text,letterSpacing:-0.2}}>{cur?.label}</div>
            <div style={{fontSize:11,color:C.textMuted,marginTop:1}}>Warehouse Risk Intelligence · APAC FMCG</div>
          </div>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <span style={{fontSize:11,color:C.textMuted,background:C.bg2,
              border:`1px solid ${C.border}`,padding:"5px 10px",borderRadius:7,
              fontFamily:"monospace",letterSpacing:0.3}}>{scoreDate}</span>

            <BtnGhost label="⟲ Refresh" onClick={()=>refreshAll().catch(console.error)} />
            <BtnPrimary label="⟳ Run Engine" onClick={()=>refreshAll().catch(console.error)} disabled={loading} />

            <button onClick={()=>setDark(!dark)} className="theme-toggle" title={dark?"Light mode":"Dark mode"}>
              {dark?"☀️":"🌙"}
            </button>
          </div>
        </div>

        <div style={{flex:1,overflowY:"auto",padding:"18px 22px",paddingBottom:48,background:C.bg}}>
          {renderView()}
        </div>
      </div>

      {/* ─── GLOBAL CSS ───────────────────────────────────────── */}
      <style>{`
        *, *::before, *::after {
          box-sizing: border-box;
          margin: 0; padding: 0;
          transition:
            background-color 220ms ease,
            background     220ms ease,
            border-color   220ms ease,
            color          220ms ease,
            box-shadow     220ms ease,
            fill           220ms ease,
            stroke         220ms ease,
            opacity        150ms ease;
        }
        * { transition-property: background-color, background, border-color, color, box-shadow, fill, stroke, opacity; }
        html, body { height:100%; background: var(--bg); }

        .col  { display:flex; flex-direction:column; }
        .grid-2 { display:grid; grid-template-columns:1fr 1fr; }
        .grid-4 { display:grid; grid-template-columns:repeat(4,1fr); }
        .grid-65 { display:grid; grid-template-columns:1.85fr 1fr; }

        .bar-track { flex:1; height:4px; background:var(--border); border-radius:99px; overflow:hidden; }
        .bar-fill  { height:100%; border-radius:99px; transition:width 0.9s cubic-bezier(0.16,1,0.3,1); }

        .chip {
          font-size:10px; font-weight:600; padding:2px 9px; border-radius:99px;
          white-space:nowrap; font-family:monospace; letter-spacing:0.2px;
        }

        .btn-primary {
          font-size:11px; font-weight:600; padding:6px 14px; border-radius:8px;
          cursor:pointer; background:var(--accent); color:#000; border:none;
          box-shadow:0 2px 10px var(--accent-glow);
        }
        .btn-primary:hover { opacity:0.82; }
        .btn-primary:active { transform:scale(0.96); }

        .btn-ghost-active {
          font-size:12px; font-weight:600; padding:8px 16px; border-radius:8px;
          cursor:pointer; background:transparent; color:var(--text-sub);
          border:1px solid var(--border);
        }
        .btn-ghost-active:hover { border-color:var(--border-hov); }

        .btn-investigate {
          font-size:11px; font-weight:600; padding:4px 11px; border-radius:6px;
          cursor:pointer; background:var(--red-soft); color:var(--red);
          border:1px solid rgba(248,113,113,0.25);
        }
        .btn-investigate:hover { opacity:0.8; }

        .status-btn {
          font-size:11px; font-weight:500; padding:4px 11px; border-radius:6px;
          cursor:pointer; border:1px solid;
        }
        .status-btn:hover { opacity:0.75; }
        .status-btn:active { transform:scale(0.96); }

        .nav-badge {
          font-size:9px; font-weight:700; padding:1px 6px; border-radius:99px;
          background:var(--red); color:#fff; font-family:monospace;
        }

        .filter-btn {
          font-size:11px; font-weight:500; padding:5px 12px; border-radius:8px;
          cursor:pointer; background:transparent; color:var(--text-sub);
          border:1px solid var(--border);
        }
        .filter-btn:hover { border-color:var(--border-hov); color:var(--text); }
        .filter-btn.active { background:var(--accent); color:#000; border-color:var(--accent); }

        .form-label {
          font-size:11px; color:var(--text-muted); margin-bottom:5px;
          font-weight:500; display:block;
        }
        .form-input {
          width:100%; background:var(--bg); border:1px solid var(--border);
          color:var(--text); padding:9px 12px; border-radius:8px; font-size:13px;
          outline:none; font-family:inherit;
        }
        .form-input:focus { border-color:var(--accent); }
        .form-input::placeholder { color:var(--text-muted); }
        select.form-input option { background:var(--surface); color:var(--text); }

        .badge-accent {
          font-size:10px; font-weight:600; color:var(--accent);
          background:var(--accent-soft); padding:3px 9px; border-radius:6px;
          font-family:monospace; white-space:nowrap;
        }

        :root { --red-border: rgba(248,113,113,0.20); }

        .theme-toggle {
          width:34px; height:34px; border-radius:8px; cursor:pointer;
          display:flex; align-items:center; justify-content:center;
          font-size:15px; background:var(--bg2);
          border:1px solid var(--border); color:var(--text-sub);
        }
        .theme-toggle:hover { border-color:var(--border-hov); background:var(--surface-pop); }

        .pulse-dot {
          width:6px; height:6px; border-radius:50%;
          background:var(--green); box-shadow:0 0 6px var(--green-soft);
          animation:pulse 2.5s ease infinite;
        }

        ::-webkit-scrollbar { width:4px; height:4px; }
        ::-webkit-scrollbar-track { background:transparent; }
        ::-webkit-scrollbar-thumb { background:var(--border-hov); border-radius:4px; }

        @keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.45;transform:scale(0.82)} }
        button:active { transform:scale(0.96); }
      `}</style>
    </div>
  );
}