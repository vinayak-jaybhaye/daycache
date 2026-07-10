import asyncio
import random
import sys
from datetime import date, datetime, time, timedelta

from sqlalchemy.future import select

from app.core.security import hash_password
from app.db.models.collection import Collection, CollectionEntry
from app.db.models.journal import Day, JournalEntry
from app.db.models.mood import EntryMood, Mood
from app.db.models.tag import JournalTag, Tag
from app.db.models.user import User, UserSettings
from app.db.session import _get_session_factory

DIARY_INTROS = [
    "Today started off with an unexpected burst of energy, which was a welcome change from the lethargy I've been feeling all week. I actually woke up before my alarm went off, feeling completely rested and ready to tackle whatever challenges the day had in store for me.",
    "I woke up this morning feeling completely exhausted, as if the weight of the entire world was pressing down on my shoulders before I even stepped out of bed. It took an embarrassing amount of coffee just to feel somewhat functional and human again.",
    "What an absolute whirlwind of a day! From the moment I stepped out the front door, it felt like I was running a marathon at a sprinter's pace, constantly putting out fires and jumping from one urgent task to another without a second to breathe.",
    "It has been quite a while since I've experienced a day this remarkably productive and fulfilling. Everything just seemed to click into place effortlessly, and I found myself getting through my meticulously planned to-do list with a surprising amount of grace and speed.",
    "The morning started off a bit slow and sluggish, with the gray clouds outside perfectly matching my mood, but things unexpectedly picked up momentum by the early afternoon when the sun finally decided to break through the overcast sky.",
    "I seriously cannot believe how incredibly fast time has been flying by lately; it feels as though I just blinked and another entire month has completely vanished into thin air, leaving me wondering where all the days went.",
    "Today was undeniably one of the most stressful and overwhelming days I've had in recent memory, and I am profoundly relieved and grateful that it has finally come to an end.",
    "I had the rare luxury of enjoying a truly relaxing and undisturbed morning for a change, savoring my breakfast slowly and actually taking the time to read a few chapters of a book before diving into the chaos of my usual routine.",
]

DIARY_BODY = [
    "I spent the vast majority of my day deeply focused on that massive, complex project at work that has been looming over my head for weeks. After hours of intense concentration and several moments of sheer frustration, I finally managed to make some substantial, tangible progress, which is a massive relief. Afterwards, feeling a sense of accomplishment, I managed to squeeze in a quick, impromptu coffee catch-up with an old friend I haven't seen in months, which was exactly what I needed to decompress.",
    "I decided to step away from my screens and go for a long, meandering walk around the neighborhood this afternoon. The weather was surprisingly mild and pleasant, with a gentle breeze that rustled the leaves, and it gave me an uninterrupted stretch of time to just clear my cluttered mind. I spent the time reflecting on my long-term goals and planning out the concrete steps I need to take over the next few months to actually achieve them.",
    "Unfortunately, almost my entire day was completely eaten up by a grueling marathon of back-to-back meetings that seemed to drag on endlessly without any clear resolutions. It is so incredibly draining to sit through hours of discussions when you have a mountain of actual work waiting for you. I barely even had a spare moment to grab a quick bite for lunch, let alone make a dent in my overwhelming inbox.",
    "I intentionally decided to take things easy today and finally caught up on some much-needed leisure reading that I've been putting off. I cracked open the first few pages of that highly recommended sci-fi novel I've been meaning to get to for ages, and to my delight, the intricate world-building and compelling characters have already completely hooked me in.",
    "I finally dragged myself back to the gym for the first time in over a week, and honestly, it felt absolutely amazing to get my body moving and my heart rate up again. The endorphin rush afterward was phenomenal, even though I am acutely aware that I am going to be painfully sore and regretting those heavy squats when I try to get out of bed tomorrow morning.",
    "This evening turned out to be unexpectedly special and heartwarming. We decided against going out and instead collaborated on cooking a massive, elaborate dinner from scratch right in our own kitchen, chopping vegetables and simmering sauces while listening to our favorite nostalgic playlists. It's the simple, intimate moments like this that I truly cherish more than anything else.",
    "I must have spent at least four consecutive hours staring at my monitor, meticulously debugging a bizarre and deeply embedded issue in the codebase. It was an incredibly frustrating and tedious process of trial and error, testing hypotheses that repeatedly failed, but that sudden, euphoric 'aha!' moment when I finally pinpointed the elusive bug made the entire ordeal entirely worth it.",
]

DIARY_CONCLUSIONS = [
    "Anyway, my eyes are getting heavy, so I am definitively heading to bed early tonight. I really need to catch up on some serious sleep if I want to be even remotely functional tomorrow.",
    "Despite the minor setbacks, I am actually feeling pretty optimistic and energized about what tomorrow might bring. Let's just wait and see how everything unfolds.",
    "Right now, my only plan is to completely turn off my brain, sink into the couch, watch a mindless episode of my favorite comfort show, and properly unwind.",
    "I am sincerely crossing my fingers and hoping for a significantly better, less chaotic day tomorrow, because I don't think I have the stamina for a repeat of today.",
    "As I write this, I find myself feeling incredibly and profoundly grateful for all the wonderful people and opportunities in my life right now.",
    "Looking ahead, I absolutely need to make sure that I intentionally prioritize rest and actual recovery this upcoming weekend, rather than filling my schedule with more obligations.",
]

TAGS_DATA = [
    ("work", "#E57373"),
    ("personal", "#64B5F6"),
    ("travel", "#81C784"),
    ("health", "#FFB74D"),
    ("family", "#9575CD"),
    ("fitness", "#4DB6AC"),
    ("learning", "#FF8A65"),
    ("ideas", "#F06292"),
    ("friends", "#4DD0E1"),
    ("finances", "#DCE775"),
]

MOODS_DATA = [
    ("happy", "#FFE082"),
    ("focused", "#90CAF9"),
    ("tired", "#BCAAA4"),
    ("stressed", "#EF9A9A"),
    ("creative", "#CE93D8"),
    ("calm", "#80CBC4"),
    ("anxious", "#FFCC80"),
]

COLLECTIONS_DATA = [
    ("deep thoughts", "A place for deep reflections", "brain"),
    ("gratitude", "Things I am thankful for", "heart"),
    ("travel logs", "Memories from trips", "plane"),
    ("dreams", "Dream journal", "moon"),
    ("work notes", "Professional development", "briefcase"),
    ("fitness journey", "Workouts and health", "activity"),
    ("ideas", "Random sparks of inspiration", "lightbulb"),
    ("book reviews", "Books I've read", "book"),
    ("family", "Moments with family", "users"),
    ("food diary", "Delicious meals and recipes", "coffee"),
]

LOCATIONS = [
    {"name": "San Francisco, CA", "lat": 37.7749, "lon": -122.4194},
    {"name": "New York, NY", "lat": 40.7128, "lon": -74.0060},
    {"name": "London, UK", "lat": 51.5074, "lon": -0.1278},
    {"name": "Tokyo, Japan", "lat": 35.6762, "lon": 139.6503},
    {"name": "Home", "lat": None, "lon": None},
]

WEATHERS = [
    {"condition": "Sunny", "temperature": 72},
    {"condition": "Rainy", "temperature": 55},
    {"condition": "Cloudy", "temperature": 60},
    {"condition": "Snowy", "temperature": 28},
    {"condition": "Clear", "temperature": 65},
]


def generate_entry_content():
    intro = random.choice(DIARY_INTROS)
    body = random.choice(DIARY_BODY)
    conclusion = random.choice(DIARY_CONCLUSIONS)

    text = f"{intro}\n\n{body}\n\n{conclusion}"

    # Very simple Tiptap JSON structure
    content_json = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": intro}]},
            {"type": "paragraph", "content": [{"type": "text", "text": body}]},
            {"type": "paragraph", "content": [{"type": "text", "text": conclusion}]},
        ],
    }

    word_count = len(text.split())

    return content_json, text, word_count


async def seed(num_entries: int, embed_entries: bool = False):
    factory = _get_session_factory()

    async with factory() as session:
        # 1. Setup User
        print("Checking user...")
        result = await session.execute(
            select(User).where(User.email == "user@daycache.com")
        )
        user = result.scalars().first()

        if not user:
            print("Creating user 'user@daycache.com'...")
            user = User(
                email="user@daycache.com",
                display_name="Test User",
                password_hash=hash_password("password"),
                is_verified=True,
            )
            session.add(user)
            await session.flush()

            settings = UserSettings(
                user_id=user.id,
                locale="en-US",
                timezone="UTC",
                theme="system",
                week_starts_on=1,
                ai_enabled=True,
                editor_font="inter",
                content_language="en",
                ai_persona_name="Mira",
            )
            session.add(settings)
            await session.flush()
        else:
            print(f"User {user.email} already exists.")

        # 2. Setup System Moods
        print("Checking moods...")
        moods_in_db = []
        for name, color in MOODS_DATA:
            result = await session.execute(select(Mood).where(Mood.name == name))
            mood = result.scalars().first()
            if not mood:
                mood = Mood(name=name, color=color)
                session.add(mood)
                await session.flush()
            moods_in_db.append(mood)

        # 3. Setup Tags
        print("Checking tags...")
        tags_in_db = []
        for name, color in TAGS_DATA:
            result = await session.execute(
                select(Tag).where(Tag.name == name, Tag.user_id == user.id)
            )
            tag = result.scalars().first()
            if not tag:
                tag = Tag(user_id=user.id, name=name, color=color)
                session.add(tag)
                await session.flush()
            tags_in_db.append(tag)

        # 4. Setup Collections
        print("Checking collections...")
        collections_in_db = []
        for name, desc, icon in COLLECTIONS_DATA:
            result = await session.execute(
                select(Collection).where(
                    Collection.name == name, Collection.user_id == user.id
                )
            )
            col = result.scalars().first()
            if not col:
                col = Collection(
                    user_id=user.id, name=name, description=desc, icon=icon
                )
                session.add(col)
                await session.flush()
            collections_in_db.append(col)

        # 5. Generate Entries
        print(f"Generating {num_entries} entries over the last 2 years...")

        end_date = date.today()
        start_date = end_date - timedelta(days=730)

        # Pick a random set of days to have entries
        total_days = (end_date - start_date).days

        arq_pool = None
        if embed_entries:
            from app.api.deps import get_arq_pool

            arq_pool = await get_arq_pool()

        entries_created = 0

        while entries_created < num_entries:
            # Pick a random day
            random_day_offset = random.randint(0, total_days)
            target_date = start_date + timedelta(days=random_day_offset)

            # Decide how many entries for this day (1 to 5)
            entries_for_day = random.randint(1, min(5, num_entries - entries_created))

            # Check if Day exists
            result = await session.execute(
                select(Day).where(Day.user_id == user.id, Day.date == target_date)
            )
            day = result.scalars().first()

            if not day:
                day = Day(
                    user_id=user.id,
                    date=target_date,
                    weather=random.choice(WEATHERS),
                    location=random.choice(LOCATIONS),
                )
                session.add(day)
                await session.flush()

            for _ in range(entries_for_day):
                content_json, text_val, wc = generate_entry_content()

                entry_time = datetime.combine(
                    target_date, time(random.randint(6, 23), random.randint(0, 59))
                )

                entry = JournalEntry(
                    day_id=day.id,
                    content=content_json,
                    content_text=text_val,
                    word_count=wc,
                    is_favorite=(random.random() < 0.1),  # 10% chance of being favorite
                )

                # Override created_at for history
                entry.created_at = entry_time
                entry.updated_at = entry_time

                session.add(entry)
                await session.flush()

                # Add Tags (3-4)
                num_tags = random.randint(3, 4)
                selected_tags = random.sample(tags_in_db, num_tags)
                for t in selected_tags:
                    session.add(JournalTag(journal_entry_id=entry.id, tag_id=t.id))

                # Add Mood (1)
                selected_mood = random.choice(moods_in_db)
                session.add(
                    EntryMood(
                        journal_entry_id=entry.id,
                        mood_id=selected_mood.id,
                        intensity=random.randint(1, 10),
                    )
                )

                # Add Collections (0-2)
                num_collections = random.randint(0, 2)
                if num_collections > 0:
                    selected_cols = random.sample(collections_in_db, num_collections)
                    for i, c in enumerate(selected_cols):
                        session.add(
                            CollectionEntry(
                                collection_id=c.id,
                                journal_entry_id=entry.id,
                                position=i,
                            )
                        )

                entries_created += 1

                if arq_pool:
                    try:
                        await arq_pool.enqueue_job(
                            "process_journal_entry_embeddings",
                            str(entry.id),
                            entry.version,
                            _queue_name="embedding_queue",
                        )
                    except Exception as e:
                        print(f"Failed to enqueue embedding for {entry.id}: {e}")

        print(f"Successfully generated {entries_created} entries.")
        await session.commit()


if __name__ == "__main__":
    embed_entries = False
    if len(sys.argv) > 1:
        num_entries = int(sys.argv[1])
        if len(sys.argv) > 2:
            embed_entries = sys.argv[2].lower() in ["y", "yes", "true", "1"]
    else:
        num_entries = input("How many entries to add? (Max 1000): ")
        try:
            num_entries = int(num_entries)
        except ValueError:
            print("Invalid number. Exiting.")
            sys.exit(1)

        embed_ans = input("Do you want to queue embeddings for these entries? (y/N): ")
        embed_entries = embed_ans.lower() in ["y", "yes", "true"]

    num_entries = min(max(1, num_entries), 1000)
    asyncio.run(seed(num_entries, embed_entries))
