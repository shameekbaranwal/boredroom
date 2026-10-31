import { go } from '../router'
import { Fx, Header, Nav, useApp } from '../ui'
import { JoinByCode } from './Desk'

// what the review would show, greyed: a taste of the standings, not real people
const GHOSTS: [string, string, string][] = [['1', 'the chair', '12'], ['2', 'someone from the group chat', '9'], ['=3', 'you, eventually', '7'], ['=3', 'the one who only plays wordle', '7']]

/** The review with no board behind it: an empty sheet that says what goes here, and the
 *  two ways to get a board. */
export default function NoBoardReview() {
  const { me } = useApp()
  return (
    <div className="app">
      <Header title="review.xlsx" meta={me.username} />
      <Fx fn="review" args={[['board', 'none yet'], ['period', 'today']]} />
      <div className="bd">
        <div className="card">
          <b>no board, no review.</b>
          <small>the review ranks you against the people on a board: daily wins, averages, records, tenure, head-to-heads. join your friends' board, or start one and send them the invite.</small>
        </div>
        <div className="sec">daily wins · today <span className="sec-n">· a preview</span></div>
        {GHOSTS.map(([n, who, v]) => (
          <div key={who} className="wr ghost" aria-hidden="true">
            <span className="n">{n}</span><span className="av ghost-av" /><span className="who">{who}</span><b className="v">{v}</b><span className="t2">wins</span>
          </div>
        ))}
        <div className="field"><JoinByCode label="join your friends' board: type the three words from their invite" /></div>
        <div><button className="btn ghost" onClick={() => go('/new')}>start a board →</button></div>
      </div>
      <Nav on="review" />
    </div>
  )
}
