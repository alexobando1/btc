import type { Stats } from '../types'

interface Achievement {
  id: string
  icon: string
  name: string
  desc: string
  unlock: (s: Stats) => boolean
  rarity: 'common' | 'rare' | 'epic' | 'legendary'
}

const ACHIEVEMENTS: Achievement[] = [
  { id: 'first_blood',  icon: '🩸', name: 'First Blood',   desc: 'Place your first trade',           unlock: s => s.total_trades >= 1,           rarity: 'common'    },
  { id: 'hat_trick',   icon: '🎩', name: 'Hat Trick',     desc: '3 winning trades',                 unlock: s => s.wins >= 3,                   rarity: 'common'    },
  { id: 'hot_streak',  icon: '🔥', name: 'Hot Streak',    desc: '5 win streak',                     unlock: s => s.streak >= 5,                 rarity: 'rare'      },
  { id: 'whale',       icon: '🐋', name: 'Whale',         desc: 'Trade > $100 in single position',  unlock: s => s.total_invested >= 100,       rarity: 'rare'      },
  { id: 'sharp',       icon: '🎯', name: 'Sharp',         desc: '70%+ win rate (min 10 trades)',    unlock: s => s.total_trades >= 10 && s.win_rate >= 0.7, rarity: 'epic' },
  { id: 'century',     icon: '💯', name: 'Century',       desc: '+$100 realized P&L',              unlock: s => s.realized_pnl >= 100,         rarity: 'epic'      },
  { id: 'degen',       icon: '🤖', name: 'Full Degen',    desc: '50 total trades',                  unlock: s => s.total_trades >= 50,          rarity: 'rare'      },
  { id: 'legend',      icon: '👑', name: 'Legend',        desc: '10,000 XP earned',                 unlock: s => s.xp >= 10000,                 rarity: 'legendary' },
  { id: 'grinder',     icon: '⚙️', name: 'Grinder',       desc: 'Bot ran for 7 days straight',      unlock: s => s.total_trades >= 20,          rarity: 'common'    },
  { id: 'oracle',      icon: '🔮', name: 'Oracle',        desc: '80%+ win rate (min 20 trades)',    unlock: s => s.total_trades >= 20 && s.win_rate >= 0.8, rarity: 'legendary' },
]

const RARITY_COLORS: Record<string, string> = {
  common:    '#5a6080',
  rare:      '#00d4ff',
  epic:      '#a855f7',
  legendary: '#ffcc00',
}

function AchievementBadge({ a, unlocked }: { a: Achievement; unlocked: boolean }) {
  const color = unlocked ? RARITY_COLORS[a.rarity] : '#2a2d40'
  return (
    <div
      className={`achievement ${unlocked ? '' : 'locked'}`}
      style={{
        border: unlocked ? `1px solid ${color}44` : '1px solid var(--border)',
        boxShadow: unlocked ? `0 0 12px ${color}22, inset 0 0 8px ${color}11` : 'none',
      }}
      title={`${a.name}: ${a.desc}${unlocked ? '' : ' (locked)'}`}
    >
      <span className="icon">{a.icon}</span>
      <span className="name" style={{ color: unlocked ? color : 'var(--text-dim)' }}>{a.name}</span>
      {unlocked && (
        <span style={{
          fontSize: 6, color: color, letterSpacing: '0.1em',
          textTransform: 'uppercase', fontWeight: 700,
        }}>
          {a.rarity}
        </span>
      )}
    </div>
  )
}

interface Props {
  stats: Stats | null
}

export function Achievements({ stats }: Props) {
  const s = stats ?? {
    open_positions: 0, total_invested: 0, unrealized_pnl: 0, realized_pnl: 0,
    total_trades: 0, win_rate: 0, wins: 0, losses: 0, xp: 0, streak: 0,
  }

  const unlocked = ACHIEVEMENTS.filter(a => a.unlock(s))
  const locked = ACHIEVEMENTS.filter(a => !a.unlock(s))

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="panel-header">
        <div className="dot" style={{ background: 'var(--yellow)', boxShadow: '0 0 8px #ffcc0088' }} />
        ACHIEVEMENTS
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, fontSize: 9 }}>
          <span style={{ color: 'var(--green)' }}>{unlocked.length} unlocked</span>
          <span style={{ color: 'var(--text-dim)' }}>/ {ACHIEVEMENTS.length}</span>
        </div>
      </div>

      {/* Progress */}
      <div style={{ padding: '6px 12px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 9, color: 'var(--text-dim)' }}>Collection progress</span>
          <span style={{ fontSize: 9, color: 'var(--yellow)' }}>{Math.round(unlocked.length / ACHIEVEMENTS.length * 100)}%</span>
        </div>
        <div className="progress-bar">
          <div className="progress-bar-fill" style={{
            width: `${unlocked.length / ACHIEVEMENTS.length * 100}%`,
            background: 'linear-gradient(90deg, #a855f7, #ffcc00)',
            boxShadow: '0 0 8px #ffcc0066',
          }} />
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 10px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {[...unlocked, ...locked].map(a => (
            <AchievementBadge key={a.id} a={a} unlocked={a.unlock(s)} />
          ))}
        </div>
      </div>
    </div>
  )
}
