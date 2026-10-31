"""Invites: three words that open a board ("smug-walrus-adjourns").

An invite is its own row. Every member hands out their own, so the board knows who
brought whom, and each lasts a day (LIFETIME) unless its owner swaps it for a new one sooner. The words are random, unique across every
invite ever made, and read as a tiny board-meeting sentence: adjective, noun, verb.
Codes made before word codes existed still work as they were typed.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import throttle
from .errors import fail
from .models import Board, Invite, Person, utcnow

ADJECTIVES = """
able absent agile amber ample ancient antsy apt arch ardent artful astute avid awake
balmy bashful beefy bendy bitter bland bleak blithe blond blunt bold bonny bossy bouncy
brainy brash brave breezy brief bright brisk broad bubbly bulky bumpy burly busy
calm candid canny chatty cheeky cheery chief chilly chirpy chubby civic clever cloudy
clumsy cocky comfy cosmic cosy crafty cranky crisp cuddly curly curt dainty damp dapper
daring dazed deadpan decent deft dense dewy dim dizzy dopey dotty dour drowsy dusty
eager early earnest easy edgy eerie elated elder elfin epic even exact fabled fair faint
fancy feisty fervent fiery final fizzy flaky fluffy fond formal frank frosty frugal fuzzy
gentle giddy gifted glad gleeful glossy glum gnarly golden goofy grand grassy grumpy
gusty hasty hazy hearty heroic hidden hollow honest humble hungry husky icy idle jaunty
jazzy jolly jumpy keen kind kooky lanky late lavish lazy lean leafy legal lofty lone
loud lucky lumpy lunar lusty mellow merry messy mighty mild minty misty modest moody
mossy muddy muggy murky musty naive neat needy nerdy nifty nimble noble nosy novel
odd oily olden open ornate pale patchy peppy perky petite placid plain plucky plush
polite portly posh prim proper proud punchy quaint quick quiet quirky rainy rapid rare
regal rosy rowdy royal rugged rustic rusty salty sandy sassy scrappy sharp shiny shy
silent silky silly sleek sleepy slick sly smug snappy snug snowy soggy solemn sour
sparse spicy spiffy spry stately steady stern stocky stout sturdy sublime sulky sunny
super surly svelte swanky sweet swift tacky tame tangy tardy taut tender terse thrifty
tidy tiny tipsy tired toasty trusty tubby twitchy vague vain valiant vast velvet vexed
vivid wacky wary weary wily windy wintry wise witty wobbly woolly worldly zany zesty
""".split()

NOUNS = """
aardvark acorn agenda albatross alpaca anchor antelope apricot armadillo auditor
avocado axolotl badger bagel banjo barnacle basil beaver beetle biscuit bison blender
blimp boar bobcat bonsai bookend boulder brioche buffalo bulldog bumblebee bunny burrito
buzzard cabbage cactus camel canary candle capybara caribou carrot cashew catfish
cauldron chair chameleon cheetah chestnut chinchilla chipmunk clam clipboard cobra
coconut comet compass cookie cormorant cougar coyote crab crayon cricket crocodile
crouton crumpet cucumber cupcake dachshund dingo dolphin donkey dormouse dragonfly
dumpling eagle eggplant elephant elk emu falcon ferret fig finch flamingo flounder
gazelle gecko gerbil gherkin gibbon giraffe goat goose gopher gorilla grapefruit
grasshopper gravy hamster hedgehog heron hippo hornet hyena ibex iguana impala jackal
jaguar jellyfish kangaroo kettle kiwi koala kumquat ladle lemming lemur leopard lizard
llama lobster locust lynx macaw magpie mallard manatee mango marmot meerkat memo
minnow mole mongoose moose mosquito muffin mussel narwhal newt noodle nutmeg ocelot
octopus okapi omelette opossum orca ostrich otter owl oyster pancake panda pangolin
panther papaya parrot parsnip peacock pelican penguin pepper pheasant pickle pigeon
piranha pistachio platypus plum pony porcupine possum potato pretzel puffin pug puma
pumpkin quail quokka rabbit raccoon radish raven reindeer rhino robin rooster salmon
sardine scallop scone seagull seahorse sloth snail sparrow spatula sponge squid
squirrel stapler starfish stork sturgeon swan tadpole tapir teapot termite thimble
tiger toad toaster tortoise toucan trout truffle tuba tulip turkey turnip turtle
unicorn urchin vole vulture waffle walnut walrus warthog wasp weasel whale wombat
woodpecker yak zebra
""".split()

VERBS = """
abstains adjourns agrees amends applauds approves argues audits bickers blinks bluffs
brainstorms briefs chairs chuckles circles clocks coasts concedes concurs confers
convenes counts dawdles debates declines defers delegates deliberates dithers doodles
dozes drafts escalates fidgets files filibusters forecasts frowns grumbles guesses
gossips hesitates huddles hums interjects invoices itemizes juggles knits lingers lobbies
loiters minutes moonlights motions mumbles mutters naps negotiates nods objects outvotes
overrules pauses pivots ponders presides procrastinates proposes quibbles quits ratifies
recaps recesses reconvenes reconsiders recounts rehearses reschedules resigns rests
reviews schemes scribbles seconds shrugs sighs signs skims slouches snacks snoozes
speculates squints stalls stammers strategizes stretches summarizes sulks synergizes
tables tallies tiptoes tinkers twiddles unpacks vetoes votes waffles whispers wiggles
winks wonders yawns
""".split()

WORDS = (set(ADJECTIVES), set(NOUNS), set(VERBS))


def new_code(s: Session) -> str:
    """Three random words no invite has used yet."""
    while True:
        code = "-".join(secrets.choice(ws) for ws in (ADJECTIVES, NOUNS, VERBS))
        if not s.scalar(select(Invite.id).where(Invite.code == code)):
            return code


def normalise(typed: str) -> str:
    """How people type the words back ("Smug Walrus adjourns", a pasted link) -> smug-walrus-adjourns."""
    typed = typed.strip().rsplit("/join/", 1)[-1]
    return "-".join(re.findall(r"[a-z]+", typed.lower()))


LIFETIME = timedelta(hours=24)


def create(s: Session, board: Board, by: Person | None, expires_at: datetime | None = None) -> Invite:
    inv = Invite(code=new_code(s), board_id=board.id, created_by=by.id if by else None,
                 expires_at=expires_at or utcnow() + LIFETIME)
    s.add(inv)
    s.flush()
    return inv


def current(s: Session, board: Board, by: Person | None = None) -> Invite:
    """The invite `by` hands out for the board: their newest live one, made if there is none.
    With no `by`, any live invite of the board's (for scripts and tests)."""
    now = utcnow()
    q = select(Invite).where(
        Invite.board_id == board.id, Invite.revoked_at.is_(None), Invite.legacy.is_(False),
        or_(Invite.expires_at.is_(None), Invite.expires_at > now))
    if by is not None:
        q = q.where(Invite.created_by == by.id)
    live = s.scalars(q.order_by(Invite.created_at.desc(), Invite.id.desc())).first()
    if live:
        return live
    # all expired or revoked: make a fresh one (callers have already committed their work)
    live = create(s, board, by)
    s.commit()
    return live


def renew(s: Session, board: Board, by: Person) -> Invite:
    """A new invite for `by`; the one they had stops working now."""
    now = utcnow()
    for old in s.scalars(select(Invite).where(Invite.board_id == board.id, Invite.created_by == by.id,
                                              Invite.revoked_at.is_(None))):
        old.revoked_at = now
    return create(s, board, by)


def retire_all(s: Session, board: Board) -> int:
    """Every live invite to the board stops working now. Returns how many there were."""
    now, n = utcnow(), 0
    for inv in s.scalars(select(Invite).where(Invite.board_id == board.id, Invite.revoked_at.is_(None))):
        inv.revoked_at, n = now, n + 1
    return n


# Wrong codes are cheap to try, so callers who keep missing are stopped: each caller after
# MISS_LIMIT misses, and everyone at once after GLOBAL_LIMIT (a spread-out guesser). Link
# previews count too, since a preview says whether a code is real.
MISS_LIMIT, GLOBAL_LIMIT, MISS_WINDOW = 20, 300, 600


def _blocked(s: Session) -> bool:
    return (throttle.count(s, f"invite:{throttle.caller()}", MISS_WINDOW) >= MISS_LIMIT
            or throttle.count(s, "invite:*", MISS_WINDOW) >= GLOBAL_LIMIT)


def _missed(s: Session) -> None:
    throttle.note(s, f"invite:{throttle.caller()}", "invite:*")


def _live(inv: Invite | None) -> bool:
    return inv is not None and inv.revoked_at is None and not (inv.expires_at and inv.expires_at <= utcnow())


def peek(s: Session, typed: str) -> Invite | None:
    """The live invite for a code, for link previews; None (the generic preview) for a
    miss, a legacy code, or a caller who's been guessing."""
    if _blocked(s):
        return None
    inv = s.scalar(select(Invite).where(Invite.code == normalise(typed)))
    if not _live(inv) or inv.legacy:
        _missed(s)
        return None
    return inv


def lookup(s: Session, typed: str) -> Invite:
    """The live invite for a code as typed, or a 404 that doesn't say why."""
    if _blocked(s):
        fail(429, "too many invite codes that didn't work. try again in a few minutes.")
    # legacy codes are case-sensitive and kept as typed; word codes forgive spacing and case
    candidates = {typed.strip()[:80], normalise(typed)} - {""}
    inv = s.scalar(select(Invite).where(Invite.code.in_(candidates))) if candidates else None
    if not _live(inv):
        _missed(s)
        fail(404, "that invite doesn't work")
    return inv
