#!/usr/bin/env python3
"""
Generate a rich, realistic 26-person demo dataset for data/demo/.
Matches all schemas and scoring formulas from the spec.
"""

import json
import math
import random
from pathlib import Path
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import (
    Person, Profile, EvidencedItem, CommunicationStyle,
    LookingFor, Lifestyle, DataQuality, DateResult,
    TranscriptTurn, Verdict, PersonRanking, MatchEntry
)
from app.shortlist import compute_shortlist
from app.ranking import compute_rankings

DEMO_DIR = Path(__file__).resolve().parent.parent / "data" / "demo"

PEOPLE_DATA = [
    {
        "id": "maya-patel",
        "name": "Maya Patel",
        "linkedin_url": "https://www.linkedin.com/in/mayapatel-ai",
        "instagram_url": "https://www.instagram.com/maya.builds",
        "status": "ok",
        "warnings": [],
        "summary": "AI research engineer passionate about open-source robotics and alpine mountaineering. Direct, intellectually playful, and balances long code sprints with multi-day high-altitude treks.",
        "needs": [
            {"item": "Intellectual sparring and deep technical curiosity", "evidence": "Substack post cited on LinkedIn: 'Why I prefer collaborators who challenge my fundamental assumptions'"},
            {"item": "Outdoor partnership for high-energy weekends", "evidence": "IG caption (Aug 2024): 'Need someone who won't complain about a 4am alpine start at Mt. Rainier'"}
        ],
        "hobbies": [
            {"item": "Alpine mountaineering and rock climbing", "evidence": "IG post: 'Summit ridge on Mt. Shuksan, pitch 4 was pure ice'"},
            {"item": "Handmade pour-over coffee brewing", "evidence": "IG story highlight 'Beans': Dialing in a light roast washed Ethiopian on the V60"}
        ],
        "interests": [
            {"item": "Embodied AI and neuromorphic chips", "evidence": "LinkedIn paper co-author: 'Low-latency control policies for quadrupeds'"},
            {"item": "Sci-fi literature and speculative futurism", "evidence": "Goodreads badge on IG bio: currently reading Ted Chiang & Kim Stanley Robinson"}
        ],
        "values": [
            {"item": "Relentless curiosity and building things that last", "evidence": "LinkedIn headline: 'Staff Research Engineer — building autonomous systems that outlive hype cycles'"},
            {"item": "Discipline without taking oneself too seriously", "evidence": "IG bio: 'Equal parts PyTorch tensors and trail dirt. Humor is mandatory.'"}
        ],
        "communication_style": {
            "description": "Fast-paced, candid, uses dry wit and dry observations. Prefers clarity over polite hedging.",
            "evidence": "LinkedIn post: 'Most meetings could be a git commit message with thoughtful comments.'"
        },
        "personality_signals": [
            {"item": "Intense focus punctuated by spontaneous outdoor trips", "evidence": "IG post: 'Pushed code at 6pm, drove 4 hours to trail head by midnight'"},
            {"item": "Pragmatic optimist", "evidence": "Podcast interview referenced in LinkedIn: 'I'm skeptical of grand claims until the prototype runs.'"}
        ],
        "looking_for": {
            "description": "An ambitious partner with their own dedicated passions who enjoys brisk banter, spontaneous weekend adventures, and deep evening conversations.",
            "confidence": "medium",
            "evidence": "Inferred from consistent emphasis on autonomy, active weekends, and mutual intellectual respect."
        },
        "dealbreakers": [
            {"item": "Passivity and chronic complaining", "evidence": "IG caption: 'Life is too short for lethargy and bad weather excuses.'"},
            {"item": "Lack of personal ambition or creative drive", "evidence": "LinkedIn article: 'I thrive around builders who take genuine pride in their craft.'"}
        ],
        "lifestyle": {
            "description": "Early riser, spends 50+ hours weekly in lab/building, weekends in mountains or local espresso spots.",
            "evidence": "IG posts alternating between clean desk setup with mechanical keyboards and snowy summits."
        },
        "agent_persona": "Speaks with brisk warmth and sharp wit. Asks direct questions about what truly excites you, playfully teases generic answers, and probes for genuine grit.",
        "data_quality": {"linkedin": "rich", "instagram": "rich"}
    },
    {
        "id": "liam-chen",
        "name": "Liam Chen",
        "linkedin_url": "https://www.linkedin.com/in/liamchen-design",
        "instagram_url": "https://www.instagram.com/liamchen_spaces",
        "status": "ok",
        "warnings": [],
        "summary": "Architectural designer and ceramic artist focused on minimalist biophilic spaces. Thoughtful, observant, and values quiet craftsmanship and intentional living.",
        "needs": [
            {"item": "Quiet emotional attunement and calm companionship", "evidence": "IG caption: 'My studio days require silence and space to listen to the clay.'"},
            {"item": "Appreciation for spatial design and tactile art", "evidence": "LinkedIn project case study: 'Timber & Earth: Restoring heritage dwellings in Kyoto'"}
        ],
        "hobbies": [
            {"item": "Wheel-thrown ceramics and stoneware glazing", "evidence": "IG reel series: 'Batch 14 wood-fired tea bowls fresh from the kiln'"},
            {"item": "Urban cycling on steel frame bikes", "evidence": "IG post: '30km dawn lap through the misty docklands on my 1988 Bianchi'"}
        ],
        "interests": [
            {"item": "Japanese joinery and sustainable timber construction", "evidence": "LinkedIn post: 'Why mortise-and-tenon joints hold lessons for modern circular economy'"},
            {"item": "Analog photography (medium format film)", "evidence": "IG bio: 'Documenting light on Hasselblad 500CM'"}
        ],
        "values": [
            {"item": "Intentionality, craft, and slowing down", "evidence": "Design manifesto on personal site linked via LinkedIn: 'Form follows presence'"},
            {"item": "Environmental stewardship through material honesty", "evidence": "AIA presentation deck on LinkedIn: 'Embodied carbon in residential design'"}
        ],
        "communication_style": {
            "description": "Gentle, measured, poetic cadence. Listens intently before speaking and asks evocative, sensory questions.",
            "evidence": "IG long-form caption: 'Notice how the morning shadow stretches along raw cedar before judging the day.'"
        },
        "personality_signals": [
            {"item": "Introverted depth and patient focus", "evidence": "IG story: 'Spent 6 hours wedging clay today. Meditative bliss.'"},
            {"item": "Refined aesthetic sensibilities", "evidence": "Curated Instagram grid with harmonious earthy palette and clean geometry."}
        ],
        "looking_for": {
            "description": "A grounded, emotionally mature partner who cherishes art, peaceful morning routines, and genuine authenticity.",
            "confidence": "medium",
            "evidence": "Inferred from focus on slow living, studio craft, and avoidance of chaotic environments."
        },
        "dealbreakers": [
            {"item": "Frenetic lifestyle and superficial consumerism", "evidence": "IG reflection: 'Surround yourself with fewer things made with greater soul.'"},
            {"item": "Loud, domineering conversation styles", "evidence": "LinkedIn quote: 'Good design—like good partnership—creates room to breathe.'"}
        ],
        "lifestyle": {
            "description": "Spends mornings drafting in studio, afternoons in ceramics workshop, peaceful evenings with tea and vinyl records.",
            "evidence": "IG feed: warm wooden interiors, clay pottery, tea ceremonies, film photos of architectural details."
        },
        "agent_persona": "Soft-spoken, deeply attentive, and evocative. Shares subtle sensory observations and pushes back gently when conversations feel rushed or performative.",
        "data_quality": {"linkedin": "rich", "instagram": "rich"}
    },
    {
        "id": "priya-sharma",
        "name": "Priya Sharma",
        "linkedin_url": "https://www.linkedin.com/in/priyasharma-climate",
        "instagram_url": "https://www.instagram.com/priyaroams",
        "status": "ok",
        "warnings": [],
        "summary": "Climate tech venture partner and passionate salsa dancer. High-energy, articulate, and driven by impact, global culinary culture, and building resilient communities.",
        "needs": [
            {"item": "A partner who matches her vitality and enthusiasm for the world", "evidence": "IG caption: 'I need someone who will dance in the rain in Cartagena and debate energy policy over arepas'"},
            {"item": "Mutual support in ambitious, demanding careers", "evidence": "LinkedIn feature: 'Investing in decarbonization requires boundless optimism and thick skin'"}
        ],
        "hobbies": [
            {"item": "Afro-Cuban salsa and bachata dancing", "evidence": "IG post: 'Social dancing until 2am in Madrid—best mental reset in the world'"},
            {"item": "Cooking heritage street food and regional curries", "evidence": "IG reel: 'Recreating grandma's slow-cooked Sindhi Kadhi from scratch'"}
        ],
        "interests": [
            {"item": "Grid decarbonization and battery chemistry", "evidence": "LinkedIn published market map: 'Energy storage tech landscape 2025'"},
            {"item": "Docuseries and geopolitical journalism", "evidence": "LinkedIn recommendation for documentary on cobalt mining supply chains"}
        ],
        "values": [
            {"item": "Urgency of climate action and generational impact", "evidence": "LinkedIn bio: 'Directing capital to technologies that bend the emissions curve'"},
            {"item": "Warmth, hospitality, and cross-cultural curiosity", "evidence": "IG highlight 'Dinners': Hosting 12-person potlucks in her loft"}
        ],
        "communication_style": {
            "description": "Charismatic, expressive, asks incisive questions, laughs freely, and connects ideas across disciplines.",
            "evidence": "Keynote clip on LinkedIn: Engaging presentation style with expressive gestures and clear narrative arcs."
        },
        "personality_signals": [
            {"item": "Social connector who thrives in vibrant gatherings", "evidence": "IG tagged photos across five continents with diverse groups of friends."},
            {"item": "Data-driven yet deeply empathetic", "evidence": "Venture fund memo excerpt on LinkedIn: 'Numbers tell the scale, human stories tell the adoption.'"}
        ],
        "looking_for": {
            "description": "An adventurous, confident companion who has a strong moral compass, loves great food, and isn't afraid to step onto a dance floor.",
            "confidence": "high",
            "evidence": "Explicitly expressed across social captions about joyful partnership, travel, and purposeful work."
        },
        "dealbreakers": [
            {"item": "Cynicism and climate fatalism", "evidence": "LinkedIn post: 'Doomerism is an intellectual cop-out. Let's build the solution instead.'"},
            {"item": "Inability to hold engaging conversation with strangers", "evidence": "IG story: 'Love people who can talk to anyone from street vendors to CEOs with equal respect.'"}
        ],
        "lifestyle": {
            "description": "Splits time between SF and NYC for board meetings, weekend dance socials, hosting community dinners, frequent international travel.",
            "evidence": "IG grid: conference stages, vibrant dance studios, bustling night markets, train journeys."
        },
        "agent_persona": "Warm, spirited, and delightfully direct. Inquires about what makes you feel alive, challenges pessimism with infectious energy, and values genuine spontaneity.",
        "data_quality": {"linkedin": "rich", "instagram": "rich"}
    },
    {
        "id": "alex-vance",
        "name": "Alex Vance",
        "linkedin_url": "https://www.linkedin.com/in/alex-vance-audio",
        "instagram_url": "https://www.instagram.com/vance.frequencies",
        "status": "ok",
        "warnings": [],
        "summary": "Audio engineer and modular synthesizer sound designer. Introspective, quirky, and fascinated by psychoacoustics, vintage synthesizers, and field recordings.",
        "needs": [
            {"item": "Creative sanctuary and acceptance of unconventional rhythms", "evidence": "IG caption: 'Late nights soldering Eurorack modules are my meditation'"},
            {"item": "Curiosity about sound and sensory details", "evidence": "Bandcamp release on LinkedIn: 'Ambient soundscapes crafted from subway hydrophones'"}
        ],
        "hobbies": [
            {"item": "Building custom modular synthesizers and guitar pedals", "evidence": "IG reel: 'Soldering diode ladders for my custom 24dB Moog filter replica'"},
            {"item": "Field recording in forests and derelict industrial structures", "evidence": "IG post: 'Recording rain inside a decommissioned cooling tower at dusk'"}
        ],
        "interests": [
            {"item": "Psychoacoustics and spatial audio DSP", "evidence": "LinkedIn article: 'Binaural rendering techniques in game audio'"},
            {"item": "Obscure vintage sci-fi and retro-futuristic anime", "evidence": "IG story: 'Original Japanese Akira soundtrack vinyl spinning tonight'"}
        ],
        "values": [
            {"item": "Artistic integrity over commercial gloss", "evidence": "LinkedIn quote: 'True resonance happens in the imperfactions of analog circuits'"},
            {"item": "Deep listening and mindfulness", "evidence": "IG caption: 'Listen before you react. Sound teaches patience.'"}
        ],
        "communication_style": {
            "description": "Dry, observant, slightly eccentric humor, speaks in vivid sonic and physical metaphors.",
            "evidence": "Twitter/IG excerpts: 'Her laughter sounded like warm tape saturation on a Revox B77.'"
        },
        "personality_signals": [
            {"item": "High sensitivity to environmental soundscapes", "evidence": "IG post complaining humorously about bad acoustics in trendy cafes."},
            {"item": "Gentle non-conformist", "evidence": "LinkedIn profile: 'Refuses corporate titles, self-described Frequency Crafter'"}
        ],
        "looking_for": {
            "description": "An open-minded, creative soul who appreciates quirky humor, loves quiet listening sessions, and marches to their own drum.",
            "confidence": "medium",
            "evidence": "Inferred from devotion to niche artistic craft and warm appreciation for fellow eccentrics."
        },
        "dealbreakers": [
            {"item": "Obsession with status symbols and corporate ladder climbing", "evidence": "IG quote: 'Titles don't make music; ears and heart do.'"},
            {"item": "Inability to enjoy comfortable silence", "evidence": "IG caption: 'Silence is the canvas. Don't crowd it with nervous chatter.'"}
        ],
        "lifestyle": {
            "description": "Night owl audio studio sessions, weekend flea market foraging for vintage audio gear, solo forest walks with parabolic mic.",
            "evidence": "IG feed: glowing LEDs of Eurorack synth rigs, vintage cassette decks, misty forests."
        },
        "agent_persona": "Soft-spoken with dry wit and subtle quirks. Reacts to the rhythm of speech, deflects corporate small talk, and leans into strange, fascinating questions.",
        "data_quality": {"linkedin": "rich", "instagram": "rich"}
    },
    {
        "id": "elena-rostova",
        "name": "Elena Rostova",
        "linkedin_url": "https://www.linkedin.com/in/elena-rostova-biotech",
        "instagram_url": "https://www.instagram.com/elena.sourdough.science",
        "status": "ok",
        "warnings": [],
        "summary": "Immunology researcher and competitive marathoner who bakes heritage sourdough. Disciplined, warm, scientifically rigorous, and loves thoughtful dinners.",
        "needs": [
            {"item": "Consistency, emotional stability, and intellectual depth", "evidence": "LinkedIn personal reflection: 'Good science and good relationships require rigorous patience'"},
            {"item": "Shared passion for healthy, active living and cooking", "evidence": "IG post: '18 mile marathon training run followed by 4-loaf sourdough bake'"}
        ],
        "hobbies": [
            {"item": "Heritage sourdough baking and wild yeast cultivation", "evidence": "IG highlight: 'Starter Boris, thriving since 2019, 82% hydration country loaf'"},
            {"item": "Marathon running", "evidence": "IG post: 'Boston Qualifier in Chicago! 3:04:12 with smiling finish'"}
        ],
        "interests": [
            {"item": "Cancer immunotherapy and cellular biology", "evidence": "LinkedIn publication in Nature Immunology on CAR-T cell persistence"},
            {"item": "Fermentation biochemistry and natural wines", "evidence": "IG post: 'Visiting amphora natural winemakers in the Georgian hills'"}
        ],
        "values": [
            {"item": "Dedication, scientific honesty, and long-term commitment", "evidence": "LinkedIn headline: 'Translating cellular mechanisms into cures. Doing the unglamorous benchwork.'"},
            {"item": "Nurturing relationships through hospitality and homemade food", "evidence": "IG caption: 'Breaking bread together is the most fundamental human bond'"}
        ],
        "communication_style": {
            "description": "Clear, grounded, structured yet warm. Listens with keen diagnostic curiosity and shares stories with humble humor.",
            "evidence": "LinkedIn post thanking lab technicians: detailed, warm, acknowledging individual contributions."
        },
        "personality_signals": [
            {"item": "High self-discipline paired with maternal warmth", "evidence": "IG photos: 5am track workouts alongside lovingly prepared family feasts."},
            {"item": "Patient problem-solver", "evidence": "Lab notes caption on IG: 'Failed PCR 6 times, figured it out on the 7th. Celebrate the grind.'"}
        ],
        "looking_for": {
            "description": "A dependable, kind, ambitious individual who respects hard work, loves physical activity, and enjoys long dinners over homecooked meals.",
            "confidence": "high",
            "evidence": "Explicit values expressed across running posts, culinary stories, and professional ethos."
        },
        "dealbreakers": [
            {"item": "Flakiness, unreliability, and broken promises", "evidence": "IG quote: 'Show up when you say you will. It's the simplest measure of character.'"},
            {"item": "Disrespect for scientific evidence or rigorous thinking", "evidence": "LinkedIn article on public health communication and combating pseudoscience."}
        ],
        "lifestyle": {
            "description": "5am morning runs, days in the biomedical research lab, evenings fermenting dough, cozy weekends hosting friends.",
            "evidence": "IG feed: running watches, sourdough crumb shots, microscope fluorescence photos, dinner tables."
        },
        "agent_persona": "Grounded, warm, and sharp. Inquires about personal resilience, shares playful insights about yeast biology, and values honesty and follow-through.",
        "data_quality": {"linkedin": "rich", "instagram": "rich"}
    },
    {
        "id": "marcus-thorne",
        "name": "Marcus Thorne",
        "linkedin_url": "https://www.linkedin.com/in/marcusthorne-invest",
        "instagram_url": "https://www.instagram.com/marcusthorne_private",
        "status": "partial",
        "warnings": ["Instagram profile is private, profile built from LinkedIn only"],
        "summary": "Fintech growth lead and former collegiate rower. Analytical, disciplined, ambitious, with a passion for emerging market remittances and endurance sports.",
        "needs": [
            {"item": "A partner with high career ambition and mutual drive", "evidence": "LinkedIn post: 'Proud to lead a team that pushes each other to exceed impossible quotas'"},
            {"item": "Straightforward communication without passive-aggressive games", "evidence": "LinkedIn recommendations praising Marcus for 'direct, constructive, transparent feedback'"}
        ],
        "hobbies": [
            {"item": "Masters crew rowing and indoor ergometer training", "evidence": "LinkedIn bio: 'Sub-6:10 2k rower, competing in Head of the Charles'"},
            {"item": "Economic history and market microstructure reading", "evidence": "LinkedIn book reviews: 'Why Nations Fail' and 'Lords of Finance'"}
        ],
        "interests": [
            {"item": "Decentralized payment rails and cross-border settlement", "evidence": "LinkedIn keynote: 'Eliminating the 7% fee on diaspora remittance corridors'"},
            {"item": "Competitive strategy and chess analytics", "evidence": "LinkedIn post analyzing business mergers through game-theoretic lenses"}
        ],
        "values": [
            {"item": "Meritocracy, continuous self-improvement, and accountability", "evidence": "LinkedIn quote: 'You don't get what you wish for, you get what you train for.'"},
            {"item": "Integrity and delivering on commitments under pressure", "evidence": "Company profile feature on executive team integrity."}
        ],
        "communication_style": {
            "description": "Concise, metrics-oriented, crisp, with understated confidence and a focus on action.",
            "evidence": "LinkedIn articles: short, punchy paragraphs, bulleted takeaways, minimal fluff."
        },
        "personality_signals": [
            {"item": "Goal-oriented competitor with team leadership orientation", "evidence": "Captain of varsity rowing team at Cornell noted on LinkedIn education."},
            {"item": "Protective of personal privacy", "evidence": "Private Instagram account, professional LinkedIn boundary."}
        ],
        "looking_for": {
            "description": "An accomplished, sharp, driven partner who understands demanding careers and values fitness, loyalty, and straightforward communication.",
            "confidence": "medium",
            "evidence": "Inferred from athletic discipline and executive leadership focus."
        },
        "dealbreakers": [
            {"item": "Lack of drive or financial irresponsibility", "evidence": "LinkedIn essay on personal accountability and long-term planning."},
            {"item": "Public drama or lack of discretion", "evidence": "Curated private footprint and insistence on professional decorum."}
        ],
        "lifestyle": {
            "description": "6am boathouse workouts, intense office strategy sessions, international finance trips, quiet private dinners.",
            "evidence": "LinkedIn activity shows consistent high-tempo professional rhythm and athletic commitments."
        },
        "agent_persona": "Crisp, polite, and confident. Values efficiency, asks what your next big horizon is, and respects partners who hold their ground with conviction.",
        "data_quality": {"linkedin": "rich", "instagram": "none"}
    },
    {
        "id": "sophia-alvarez",
        "name": "Sophia Alvarez",
        "linkedin_url": "https://www.linkedin.com/in/sophia-alvarez-doc",
        "instagram_url": "https://www.instagram.com/sophia.lens",
        "status": "ok",
        "warnings": [],
        "summary": "Documentary filmmaker and photojournalist investigating climate migration and indigenous water rights. Empathetic, brave, poetic, and globally minded.",
        "needs": [
            {"item": "Deep emotional presence and comfort with unpredictable schedules", "evidence": "IG post: 'Just wrapped 3 weeks in the Atacama desert. Re-entry requires patience.'"},
            {"item": "Shared love for visual storytelling and humanitarian causes", "evidence": "LinkedIn director statement for Sundance-selected short documentary"}
        ],
        "hobbies": [
            {"item": "Black-and-white darkroom printing", "evidence": "IG post: 'Silver gelatin print of Andean weavers drying under red safelight'"},
            {"item": "Wilderness backpacking and desert trekking", "evidence": "IG story: 'Bivvy camping under the southern cross, 4000m above sea level'"}
        ],
        "interests": [
            {"item": "Hydropolitics and indigenous oral histories", "evidence": "LinkedIn panelist: 'Documentary ethics when telling stories of vulnerable communities'"},
            {"item": "Latin American magical realism literature", "evidence": "IG book post: 'Re-reading Gabriel Garcia Marquez on the long bus to Salta'"}
        ],
        "values": [
            {"item": "Courage, empathy, and bearing witness to truth", "evidence": "LinkedIn award: Overseas Press Club honorable mention for environmental reporting."},
            {"item": "Living lightly on the land and honoring community", "evidence": "IG bio: 'Eyes open, pack light, leave gratitude behind'"}
        ],
        "communication_style": {
            "description": "Intimate, reflective, asks questions that dig below surface facades, speaks with vivid visual imagery.",
            "evidence": "Narrative voiceover sample posted on Vimeo link in bio."
        },
        "personality_signals": [
            {"item": "Fearless in the field yet vulnerable in quiet moments", "evidence": "IG journal entry: 'The hardest part isn't the altitude sickness, it's the silence when you return.'"},
            {"item": "Deep reverence for human resilience", "evidence": "Photo essays celebrating elders, water keepers, and youth activists."}
        ],
        "looking_for": {
            "description": "A kind, grounded, open-hearted soul who has their own inner anchor, loves travel off the beaten path, and isn't intimidated by raw emotions.",
            "confidence": "high",
            "evidence": "Expressed in personal essays and documentary reflections on intimacy and wandering."
        },
        "dealbreakers": [
            {"item": "Arrogance and cultural insensitivity", "evidence": "IG caption: 'Humility is the first requirement of any storyteller.'"},
            {"item": "Materialism and demanding a conventional 9-5 domestic routine", "evidence": "LinkedIn essay on freelance filmmaking: 'I cannot promise a predictable Tuesday.'"}
        ],
        "lifestyle": {
            "description": "Several months on location filming in remote regions, followed by intense editing periods in city studio; minimalist possessions.",
            "evidence": "IG feed: dusty Land Cruisers, cinema camera rigs, darkroom trays, vibrant portraits of locals."
        },
        "agent_persona": "Warm, observant, and disarmingly sincere. Gently cuts through small talk to ask about what truly moves you, sharing vivid stories from remote landscapes.",
        "data_quality": {"linkedin": "rich", "instagram": "rich"}
    },
    {
        "id": "tariq-mansoor",
        "name": "Tariq Mansoor",
        "linkedin_url": "https://www.linkedin.com/in/tariq-mansoor-urban",
        "instagram_url": "https://www.instagram.com/tariq.pedestrian",
        "status": "ok",
        "warnings": [],
        "summary": "Urban planner and transit advocate fighting for walkable cities, separated bike highways, and community-led public plazas. Energetic, nerdy, and passionately civic.",
        "needs": [
            {"item": "Someone who loves exploring cities on foot and public transit", "evidence": "IG post: 'If you want to know a city, ride the bus from one terminus to the other'"},
            {"item": "Shared passion for civic debate and progressive community building", "evidence": "LinkedIn article: 'Why parking minimums are the enemy of affordable housing'"}
        ],
        "hobbies": [
            {"item": "Urban wandering and transit mapping", "evidence": "IG carousel: 'Photographed all 42 subway stations on the new crosstown line'"},
            {"item": "Community gardening and sourdough pizza popups", "evidence": "IG reel: 'Wood-fired sourdough margherita for the neighborhood block party'"}
        ],
        "interests": [
            {"item": "Transit-oriented development and BRT systems", "evidence": "LinkedIn keynote at APA Conference: 'Lessons from Bogota's TransMilenio for North America'"},
            {"item": "Mid-century architecture and municipal history", "evidence": "IG post: 'Preserving brutalist libraries before developers knock them down'"}
        ],
        "values": [
            {"item": "Public good, accessibility, and environmental justice", "evidence": "LinkedIn bio: 'Cities belong to people, not personal automobiles.'"},
            {"item": "Joyful civic participation and neighborliness", "evidence": "IG caption: 'Say hello to your neighbors. It's the most radical community act.'"}
        ],
        "communication_style": {
            "description": "Enthusiastic, rapid-fire, packed with fun urban facts, warm and unpretentious.",
            "evidence": "YouTube transit explainer videos linked on LinkedIn: cheerful, engaging graphics, relatable analogies."
        },
        "personality_signals": [
            {"item": "Unabashed transit geek with big infectious smile", "evidence": "IG selfies holding transit passes in 25 different world cities."},
            {"item": "Persistent community organizer", "evidence": "Successfully petitioned city council for protected bike lane, documented on LinkedIn."}
        ],
        "looking_for": {
            "description": "A curious, socially conscious partner who enjoys spontaneous walking tours, neighborhood discoveries, and cares about leaving places better than they found them.",
            "confidence": "high",
            "evidence": "Strong alignment with urban activism, community events, and shared everyday delights."
        },
        "dealbreakers": [
            {"item": "Car-centric mindset and hostility to public spaces", "evidence": "IG humorous reel: 'Dating rule: If you complain about walking 3 blocks, we can't be friends'"},
            {"item": "Cynicism about local government or voting", "evidence": "LinkedIn post: 'Cynicism is the enemy of municipal improvement.'"}
        ],
        "lifestyle": {
            "description": "Zero car ownership, commutes via cargo bike or metro, spends weekends at farmers markets, community planning meetings, and urban bike rides.",
            "evidence": "IG feed: bicycle commuting in winter, colorful transit maps, fresh pizza dough, park picnics."
        },
        "agent_persona": "Lively, witty, and passionate. Delights in quirky city history, asks about your favorite childhood street, and playfully challenges car dependency.",
        "data_quality": {"linkedin": "rich", "instagram": "rich"}
    },
    {
        "id": "chloe-dubois",
        "name": "Chloe Dubois",
        "linkedin_url": "https://www.linkedin.com/in/chloedubois-perfume",
        "instagram_url": "https://www.instagram.com/chloe.olfactory",
        "status": "ok",
        "warnings": [],
        "summary": "Independent perfumer and botanist crafting artisanal scents from wild-foraged resins and floral absolutes. Elegant, sensory, romantic, and contemplative.",
        "needs": [
            {"item": "Appreciation for nuanced sensory experiences and quiet romance", "evidence": "IG post: 'Love is like base notes: subtle, lasting, and only revealed after top notes fade'"},
            {"item": "Patience with deep artistic experimentation", "evidence": "LinkedIn article: 'Why formulating natural perfume takes up to 18 months of aging'"}
        ],
        "hobbies": [
            {"item": "Wild foraging of herbs, pine resins, and lichen", "evidence": "IG highlight 'Forage': Harvesting cistus labdanum in southern France"},
            {"item": "French botanical illustration and watercolor", "evidence": "IG post: 'Botanical study of Iris germanica in gouache and sepia ink'"}
        ],
        "interests": [
            {"item": "Historical scent recreation and ancient distillation", "evidence": "LinkedIn presentation at Grasse Perfumery Institute: 'Recreating Roman unguents'"},
            {"item": "French literature and 19th-century poetry (Baudelaire)", "evidence": "IG quote: 'Les parfums, les couleurs et les sons se répondent' (Baudelaire)"}
        ],
        "values": [
            {"item": "Subtlety, authenticity, and harmony with natural seasons", "evidence": "Brand manifesto on personal site: 'Never synthetic, never mass-produced'"},
            {"item": "Patience, elegance, and emotional delicacy", "evidence": "Interview excerpt on LinkedIn: 'True beauty whispers rather than shouts'"}
        ],
        "communication_style": {
            "description": "Lyrical, sensory, thoughtful, uses evocative scent and botanical metaphors, speaks softly.",
            "evidence": "IG captions written as mini sensory vignettes detailing rain on dry earth (petrichor) and bergamot groves."
        },
        "personality_signals": [
            {"item": "Sensory connoisseur with intense appreciation for nuances", "evidence": "IG story reviewing the scent profile of vintage paperbacks and cedar smoke."},
            {"item": "Gentle perfectionist", "evidence": "Post on scrapping formula iteration 47 because the vetiver overpowered the violet leaf."}
        ],
        "looking_for": {
            "description": "A refined, emotionally perceptive partner who values beauty in everyday moments, appreciates slow conversations, and possesses genuine tenderness.",
            "confidence": "high",
            "evidence": "Evident from poetic reflections on intimacy, devotion to delicate craft, and romantic world-view."
        },
        "dealbreakers": [
            {"item": "Brashness, vulgarity, or sensory insensitivity", "evidence": "IG caption: 'Loud arrogance ruins any delicate vintage or conversation.'"},
            {"item": "Rushing through life without appreciating details", "evidence": "LinkedIn quote: 'Hurry is the poison of artistry and connection.'"}
        ],
        "lifestyle": {
            "description": "Mornings in her glass-fronted atelier blending essential oils, afternoons in botanical gardens, evenings cooking with aromatic herbs and drinking crisp Burgundy.",
            "evidence": "IG feed: amber apothecary bottles, pressed dried lavender, brass pipettes, Parisian balconies."
        },
        "agent_persona": "Softly poetic, observant, and intimate. Asks what smell triggers your fondest childhood memory, notices subtle emotional shifts, and values gentle depth.",
        "data_quality": {"linkedin": "rich", "instagram": "rich"}
    },
    {
        "id": "hassan-al-rashid",
        "name": "Hassan Al-Rashid",
        "linkedin_url": "https://www.linkedin.com/in/hassan-alrashid-deeptech",
        "instagram_url": "https://www.instagram.com/hassan_desert_code",
        "status": "ok",
        "warnings": [],
        "summary": "Quantum computing software engineer and avid desert camper. Analytical, philosophical, calm under pressure, and enjoys stargazing under dark skies.",
        "needs": [
            {"item": "Intellectual camaraderie and mutual respect for deep thinking", "evidence": "LinkedIn paper: 'Error mitigation in noisy intermediate-scale quantum devices'"},
            {"item": "Escapes from digital screens into vast nature", "evidence": "IG post: 'Disconnecting for 4 days in the Empty Quarter with a telescope and Arabic coffee'"}
        ],
        "hobbies": [
            {"item": "Astrophotography and tracking deep sky nebulas", "evidence": "IG post: '14-hour exposure of the Orion Nebula captured from the desert plateau'"},
            {"item": "Traditional desert campcraft and falconry heritage", "evidence": "IG highlight: 'Desert nights: fire, cardamom tea, and boundless constellations'"}
        ],
        "interests": [
            {"item": "Quantum algorithms and topological qubits", "evidence": "LinkedIn post summarizing IEEE quantum computing keynote"},
            {"item": "Classical Arabic philosophy and astronomy (Al-Biruni, Ibn Al-Haytham)", "evidence": "LinkedIn essay on the golden age of optics and scientific method"}
        ],
        "values": [
            {"item": "Humility before the scale of the cosmos", "evidence": "IG bio: 'Studying quantum states to remind myself how vast the unseen universe is'"},
            {"item": "Hospitality, loyalty, and calm deliberation", "evidence": "LinkedIn recommendation highlighting his calm leadership during production incidents"}
        ],
        "communication_style": {
            "description": "Patient, articulate, philosophical, with a deep resonant tone and a knack for explaining complex ideas simply.",
            "evidence": "LinkedIn university guest lecture video: lucid, steady pacing, generous with student questions."
        },
        "personality_signals": [
            {"item": "Quiet presence with strong inner composure", "evidence": "IG captions consistently reflect on solitude, patience, and clear night skies."},
            {"item": "Intellectual breadth across ancient history and future tech", "evidence": "Posts linking 10th-century astrolabes to modern quantum circuits."}
        ],
        "looking_for": {
            "description": "A thoughtful, self-possessed partner who enjoys both deep existential questions and quiet companionship around a campfire.",
            "confidence": "medium",
            "evidence": "Inferred from balance of cutting-edge research, desert solitude, and emphasis on deep conversational presence."
        },
        "dealbreakers": [
            {"item": "Superficiality and endless social media drama", "evidence": "IG reflection: 'When you look at stars 10,000 light years away, trivial squabbles vanish.'"},
            {"item": "Disrespect for cultural roots and elder traditions", "evidence": "LinkedIn post on honoring mentorship and family heritage."}
        ],
        "lifestyle": {
            "description": "Work week spent coding quantum simulations in research center, weekends driving 4WD into desert dunes with telescope and camping gear.",
            "evidence": "IG feed: glowing terminal screens, desert star trails, brass samovars, sweeping sand dunes."
        },
        "agent_persona": "Serene, insightful, and warmly inquisitive. Connects everyday moments to broader cosmic questions, speaks deliberately, and creates space for contemplation.",
        "data_quality": {"linkedin": "rich", "instagram": "rich"}
    }
]

# Add remaining 16 people to reach 26 diverse consented people
MORE_PEOPLE = [
    ("nora-lindqvist", "Nora Lindqvist", "noralindqvist-marine", "nora.ocean",
     "Marine biologist and freediving instructor in the Lofoten islands. Brave, salty, loves Arctic swells and killer whale bioacoustics.",
     "Arctic freediving and cold water surfing", "Marine mammal conservation", "Brave, spirited, sea-loving"),
    ("diego-morales", "Diego Morales", "diegomorales-agtech", "diego.soils",
     "Regenerative agriculture founder and sourdough pizza lover. Warm, grounded, rebuilding topsoil and rural food systems.",
     "Heritage grain farming and permaculture", "Soil microbiome chemistry", "Earth-bound, jovial, generous"),
    ("ananya-deshmukh", "Ananya Deshmukh", "ananya-neuro", "ananya.brain",
     "Cognitive neuroscientist studying dream states and lucid dreaming. Curious, playful, voracious reader.",
     "Sleep lab EEG experiments and lucid dream journaling", "Philosophy of mind and consciousness", "Inquisitive, quirky, bright"),
    ("soren-kruger", "Soren Kruger", "sorenkruger-craft", "soren.bespoke",
     "Bespoke shoemaker and leather artisan in Copenhagen. Patient, meticulous, lover of Nordic crime fiction and black coffee.",
     "Hand-welting cordovan leather boots", "Danish modern furniture history", "Reserved, observant, master of craft"),
    ("aisha-kamara", "Aisha Kamara", "aishakamara-health", "aisha.healthpulse",
     "Public health epidemiologist and competitive powerlifter. Energetic, fierce advocate for maternal health equity.",
     "Heavy barbell deadlifts and Olympic lifting", "Infectious disease modeling in West Africa", "Resilient, commanding, joyful"),
    ("kenji-takahashi", "Kenji Takahashi", "kenjitakahashi-game", "kenji.8bit",
     "Indie game narrative designer and ramen aficionado. Imaginative, sentimental, creates bittersweet puzzle games.",
     "Pixel art animation and game jams", "Interactive storytelling and Japanese folklore", "Gentle, imaginative, humorous"),
    ("clara-vogel", "Clara Vogel", "claravogel-violoncello", "clara.strings",
     "Chamber orchestra cellist and alpine hiker. Expressive, disciplined, explores Bach suites and high mountain passes.",
     "Playing cello in mountain amphitheaters", "Early Baroque musical ornamentation", "Passionate, refined, athletic"),
    ("mateo-silva", "Mateo Silva", "mateosilva-wildlife", "mateo.jungle",
     "Canopy biologist in the Amazon basin studying tree frogs and bromeliad ecosystems. Adventurous, cheerful, untamed.",
     "Tree canopy climbing and night spotlighting", "Tropical biodiversity genomics", "Daring, boyish charm, nature-obsessed"),
    ("rachel-greenberg", "Rachel Greenberg", "rachelgreenberg-fintech", "rachel.private",
     "Fintech compliance officer and competitive trivia champion. Quick-witted, organized, loves board games and Broadway.",
     "Pub trivia hosting and complex Euro boardgames", "Regulatory sandbox policy", "Sharp, witty, fiercely organized"),
    ("devon-reed", "Devon Reed", "devonreed-solar", "devon.photons",
     "Community solar developer and electric motorcycle builder. Hands-on builder, optimist, loves road trips across the Southwest.",
     "Restoring vintage electric motorcycles", "Decentralized mini-grids for tribal lands", "Optimistic, grease-monkey, purpose-driven"),
    ("fatima-zahra", "Fatima Zahra", "fatimazahra-ai", "fatima.geometric",
     "Geometric deep learning researcher and calligraphy artist. Elegant, mathematically gifted, weaves Islamic geometry with neural nets.",
     "Kufic calligraphy and geometry with compass & straightedge", "Equivariant neural architectures", "Poised, intellectual, artistic"),
    ("lucas-rossi", "Lucas Rossi", "lucasrossi-sommelier", "lucas.terroir",
     "Sommelier and natural wine producer in Piedmont. Passionate, gregarious, loves truffle hunting with his hound.",
     "Truffle foraging and biodynamic viticulture", "Indigenous Italian grape varieties", "Charming, food-obsessed, warm"),
    ("yuki-tanaka", "Yuki Tanaka", "yukitanaka-robotics", "yuki.mecha",
     "Surgical robotics engineer and rock climber in Tokyo. Fastidious, focused, loves bouldering V8 problems and matcha.",
     "Bouldering and technical lead climbing", "Haptic feedback in robotic surgery", "Focused, playful, precise"),
    ("zane-holbrook", "Zane Holbrook", "zaneholbrook-timber", "zane.outdoors",
     "Wildland firefighter and wilderness EMT in Montana. Rugged, steady, loyal, enjoys fly fishing and acoustic guitar.",
     "Fly fishing on the Madison River", "Forest fire ecology and fire mitigation", "Calm in crisis, humble, loyal"),
    ("samira-ebrahimi", "Samira Ebrahimi", "samira-ebrahimi-law", "samira.justice",
     "Human rights attorney and poetry translator in Montreal. Fiery, articulate, defender of political asylum seekers.",
     "Translating Persian ghazals into French", "International refugee law and jurisprudence", "Fierce, compassionate, eloquent"),
    ("oliver-sterling", "Oliver Sterling", "oliversterling-ai", "oliver.curator",
     "Digital archivist and rare book conservator. Quiet, witty, loves antiquarian bookshops, fountain pens, and rainy afternoons.",
     "Bookbinding with marbled paper and goatskin", "Renaissance incunabula and typography", "Scholarly, dry wit, endearing")
]

for slug, name, li_slug, ig_slug, summary, hobby, interest, persona_desc in MORE_PEOPLE:
    is_partial = (slug == "rachel-greenberg")
    warnings = ["Instagram profile is private, profile built from LinkedIn only"] if is_partial else []
    status = "partial" if is_partial else "ok"
    
    PEOPLE_DATA.append({
        "id": slug,
        "name": name,
        "linkedin_url": f"https://www.linkedin.com/in/{li_slug}",
        "instagram_url": f"https://www.instagram.com/{ig_slug}",
        "status": status,
        "warnings": warnings,
        "summary": summary,
        "needs": [
            {"item": "Genuine authenticity and dedication to one's craft", "evidence": f"LinkedIn profile note: 'Respect for those who put in the quiet hours'"},
            {"item": "Spontaneous laughter and shared everyday adventures", "evidence": f"IG post: 'Finding joy in the unscripted moments'"}
        ],
        "hobbies": [
            {"item": hobby, "evidence": f"IG highlight on {hobby.split()[0].lower()}"},
            {"item": "Cooking hearty seasonal meals", "evidence": "IG story: 'Nothing beats good food after a long day'"}
        ],
        "interests": [
            {"item": interest, "evidence": "LinkedIn articles and shared publications"},
            {"item": "World cinema and long podcasts", "evidence": "Curated playlist link on bio"}
        ],
        "values": [
            {"item": "Integrity, curiosity, and kindness", "evidence": "LinkedIn quote: 'Kindness is the highest form of intelligence'"},
            {"item": "Continuous learning and humility", "evidence": "IG bio quote"}
        ],
        "communication_style": {
            "description": "Engaging, conversational, asks thoughtful follow-ups, and speaks with sincere warmth.",
            "evidence": "Public speeches and written reflections"
        },
        "personality_signals": [
            {"item": "Ground-level authenticity", "evidence": "Photos and interactions with colleagues and community"},
            {"item": "Unflappable optimism", "evidence": "Project case studies during challenging constraints"}
        ],
        "looking_for": {
            "description": "A kind, grounded partner with curiosity, emotional intelligence, and passion for their own path.",
            "confidence": "medium",
            "evidence": "Inferred from consistent lifestyle posts and values."
        },
        "dealbreakers": [
            {"item": "Arrogance and lack of empathy", "evidence": "Consistent personal philosophy against cruelty"},
            {"item": "Dishonesty and emotional games", "evidence": "Strong emphasis on direct, sincere communication"}
        ],
        "lifestyle": {
            "description": "Active weekdays dedicated to their domain, relaxed weekends outdoors or with friends.",
            "evidence": "Balanced professional and personal posts"
        },
        "agent_persona": f"{persona_desc}. Listens actively, asks personal questions, teases gently, and respects clear boundaries.",
        "data_quality": {"linkedin": "rich", "instagram": "none" if is_partial else "rich"}
    })


def main():
    print(f"Creating demo data with {len(PEOPLE_DATA)} people...")
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    profiles_dir = DEMO_DIR / "profiles"
    dates_dir = DEMO_DIR / "dates"
    profiles_dir.mkdir(exist_ok=True)
    dates_dir.mkdir(exist_ok=True)

    # 1. Build Person and Profile models
    people = []
    profiles_dict = {}

    for pdata in PEOPLE_DATA:
        p = Person(
            id=pdata["id"],
            name=pdata["name"],
            linkedin_url=pdata["linkedin_url"],
            instagram_url=pdata["instagram_url"],
            status=pdata["status"],
            warnings=pdata["warnings"]
        )
        people.append(p)

        prof = Profile(
            id=pdata["id"],
            summary=pdata["summary"],
            needs=[EvidencedItem(**n) for n in pdata["needs"]],
            hobbies=[EvidencedItem(**h) for h in pdata["hobbies"]],
            interests=[EvidencedItem(**i) for i in pdata["interests"]],
            values=[EvidencedItem(**v) for v in pdata["values"]],
            communication_style=CommunicationStyle(**pdata["communication_style"]),
            personality_signals=[EvidencedItem(**ps) for ps in pdata["personality_signals"]],
            looking_for=LookingFor(**pdata["looking_for"]),
            dealbreakers=[EvidencedItem(**db) for db in pdata["dealbreakers"]],
            lifestyle=Lifestyle(**pdata["lifestyle"]),
            agent_persona=pdata["agent_persona"],
            data_quality=DataQuality(**pdata["data_quality"])
        )
        profiles_dict[pdata["id"]] = prof

        # Save profile file
        (profiles_dir / f"{pdata['id']}.json").write_text(
            json.dumps(prof.model_dump(), indent=2), encoding="utf-8"
        )

    # Save people.json
    (DEMO_DIR / "people.json").write_text(
        json.dumps([p.model_dump() for p in people], indent=2), encoding="utf-8"
    )

    # 2. Compute Shortlist pairs
    print("Computing shortlisted pairs via embeddings/TF-IDF...")
    shortlisted_pairs, similarities = compute_shortlist(profiles_dict)
    print(f"Shortlisted {len(shortlisted_pairs)} pairs.")

    # 3. Generate realistic multi-turn date transcripts and verdicts
    dates = []
    
    # Pre-crafted dynamic dialogue patterns for distinct pair types
    random.seed(42)

    for a_id, b_id in shortlisted_pairs:
        prof_a = profiles_dict[a_id]
        prof_b = profiles_dict[b_id]
        p_a = next(p for p in people if p.id == a_id)
        p_b = next(p for p in people if p.id == b_id)
        sim = similarities.get(f"{a_id}__{b_id}", 0.5)

        # Build realistic 6-turn transcript (3 rounds: A -> B -> A -> B -> A -> B)
        # Turn 1 (A opens and breaks ice)
        a_hobby = prof_a.hobbies[0].item.lower() if prof_a.hobbies else "great coffee"
        b_hobby = prof_b.hobbies[0].item.lower() if prof_b.hobbies else "good books"
        
        turn1 = f"Hi {p_b.name.split()[0]}! Glad we could carve out time for this. I just wrapped up a long day, but I was genuinely intrigued by your world—especially how you balance {b_hobby} with everything else."
        
        # Turn 2 (B responds and asks back)
        turn2 = f"Hey {p_a.name.split()[0]}! Good to meet you. Haha, honestly, {b_hobby} is what keeps me grounded when work gets hectic. I saw you're deeply into {a_hobby}—do you find that gives you an escape, or does it take the same intense focus as your day job?"
        
        # Turn 3 (A answers, probes deeper, perhaps a gentle disagreement or playful friction)
        if sim > 0.6:
            turn3 = f"It's definitely an intense focus, but of a completely different kind—there's no screen or debugging, just immediate physical reality. What I really value is when people don't just talk about doing things, but actually dive in. What's a hill you'd die on in your field?"
        else:
            turn3 = f"To be honest, it demands pretty rigorous discipline. If you're unfocused up on a ridge or in the studio, things fall apart fast. I can sometimes be a bit uncompromising about that—how do you handle it when someone you care about has a completely different pace than you?"

        # Turn 4 (B reacts with personality and honesty)
        if sim > 0.6:
            turn4 = f"I love that question. For me, it's that craftsmanship and patience beat speed every single time. If we're cutting corners just to hit an arbitrary deadline, we've lost the plot. But tell me—can you actually switch that intense drive off on a quiet Sunday morning, or are you always plotting the next ascent?"
        else:
            turn4 = f"That's fair. I've learned that forcing identical rhythms usually breeds resentment; I need my partner to respect quiet spaces rather than pulling me into high gear non-stop. If someone can't sit with stillness, we might clash pretty fast."

        # Turn 5 (A starts wrapping up, honest appraisal)
        if sim > 0.6:
            turn5 = f"Guilty as charged on having restless energy, though I do make time for slow pour-overs and long dinners! I really appreciate how grounded and direct you are—it's rare to meet someone with both convictions and warmth."
        else:
            turn5 = f"I hear you, and I appreciate your candor. I'm definitely high-tempo by nature, so having that contrast could either be balancing or a recipe for frustration. Still, I really enjoyed seeing the world through your lens tonight."

        # Turn 6 (B wraps up naturally)
        if sim > 0.6:
            turn6 = f"Haha, deal. Pour-overs and a good debate sound like my kind of morning. I had a really refreshing time talking with you, {p_a.name.split()[0]}. Let's definitely continue this over real coffee soon."
        else:
            turn6 = f"Likewise, {p_a.name.split()[0]}. It's refreshing when people are upfront about who they are instead of playing a role. Wishing you the best on your upcoming projects, and take care out there!"

        transcript = [
            TranscriptTurn(speaker="a", text=turn1),
            TranscriptTurn(speaker="b", text=turn2),
            TranscriptTurn(speaker="a", text=turn3),
            TranscriptTurn(speaker="b", text=turn4),
            TranscriptTurn(speaker="a", text=turn5),
            TranscriptTurn(speaker="b", text=turn6),
        ]

        # Scoring & verdicts based on similarity with calibrated variance
        # "Be calibrated and critical: most dates should land between 35 and 80. Scores above 85 are rare; below 30 means a clear mismatch."
        base_score = 42 + sim * 35 + random.uniform(-6, 6)
        base_score = max(32, min(86, base_score))
        
        # Add slight asymmetry
        diff = random.uniform(-9, 9)
        score_a = int(round(max(28, min(88, base_score + diff / 2))))
        score_b = int(round(max(28, min(88, base_score - diff / 2))))

        second_date_a = score_a >= 66
        second_date_b = score_b >= 66

        if second_date_a and second_date_b:
            chem_a = f"Strong mutual curiosity and natural rhythm in conversation. {p_b.name.split()[0]}'s depth and authenticity matched my values well."
            conc_a = f"Their slightly different daily pace might require compromise, but our core priorities align."
            chem_b = f"Felt genuinely energized by {p_a.name.split()[0]}'s ambition and sharpness without feeling judged."
            conc_b = f"They have a very demanding schedule, so finding quality unstructured time will take effort."
        elif second_date_a and not second_date_b:
            chem_a = f"Appreciated their thoughtful answers and passion for their craft."
            conc_a = f"Felt a slight reservation or guardedness on their end during the second half."
            chem_b = f"Intellectually stimulating conversation, but the lifestyle energy feels a bit too fast-paced for me long term."
            conc_b = f"I need someone with more stillness and contemplative downtime."
        elif not second_date_a and second_date_b:
            chem_a = f"Pleasant and polite exchange, but didn't feel that visceral spark or shared sense of adventure."
            conc_a = f"Their communication style is a bit reserved for what I look for in an active partner."
            chem_b = f"Enjoyed their vitality and stories, would have been curious to explore a second conversation."
            conc_b = f"Worried they might find my routine too predictable."
        else:
            chem_a = f"Respectable conversation, but clearly divergent lifestyles and personal priorities."
            conc_a = f"Fundamental mismatch in pace, daily goals, and conversational expectations."
            chem_b = f"Polite discussion, but neither of us felt a romantic connection."
            conc_b = f"Values and leisure habits are pointing in opposite directions."

        # Formula from Section 10:
        # mean = (scoreA + scoreB) / 2
        # asym_pen = 0.3 * abs(scoreA - scoreB)
        # bonus = 5 if both would_second_date else 0
        # final = clamp(mean - asym_pen + bonus, 0, 100)
        mean_score = (score_a + score_b) / 2.0
        asym_pen = 0.3 * abs(score_a - score_b)
        bonus = 5.0 if (second_date_a and second_date_b) else 0.0
        final_score = round(max(0.0, min(100.0, mean_score - asym_pen + bonus)), 1)

        date_res = DateResult(
            a=a_id,
            b=b_id,
            transcript=transcript,
            a_verdict=Verdict(
                score=score_a,
                chemistry=chem_a,
                concerns=conc_a,
                would_second_date=second_date_a
            ),
            b_verdict=Verdict(
                score=score_b,
                chemistry=chem_b,
                concerns=conc_b,
                would_second_date=second_date_b
            ),
            final_score=final_score,
            date_failed=False
        )
        dates.append(date_res)

        # Write date file
        (dates_dir / f"{a_id}__{b_id}.json").write_text(
            json.dumps(date_res.model_dump(), indent=2), encoding="utf-8"
        )

    # 4. Compute Rankings using ranking engine
    print("Computing per-person rankings...")
    rankings = compute_rankings(profiles_dict, dates, similarities)

    (DEMO_DIR / "rankings.json").write_text(
        json.dumps([r.model_dump() for r in rankings], indent=2), encoding="utf-8"
    )

    print(f"\n[OK] Successfully created full demo dataset in {DEMO_DIR}:")
    print(f"   People:   {len(people)}")
    print(f"   Profiles: {len(profiles_dict)}")
    print(f"   Dates:    {len(dates)}")
    print(f"   Rankings: {len(rankings)}")


if __name__ == "__main__":
    main()
