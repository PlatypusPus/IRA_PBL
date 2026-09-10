# Graph Report - IRPBL  (2026-09-07)

## Corpus Check
- Corpus is ~35,287 words - fits in a single context window. You may not need a graph.

## Summary
- 861 nodes · 1494 edges · 66 communities (60 shown, 4 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 72 edges (avg confidence: 0.87)
- Token cost: 375,548 input · 0 output

## Community Hubs (Navigation)
- Database Layer & Value Objects
- Weekly Digest Pipeline
- MCP Agent Server
- Chat Search UI
- shadcn Avatar & Menu Primitives
- WhatsApp Bridge (Baileys)
- Number Linking & API Key Dialogs
- Password Hashing & Sessions
- shadcn Component Registry Config
- Adapter Contract (Inward Dependency)
- Document Download & Account Routes
- WhatsApp Command Handling (/find, /get)
- TypeScript App Compiler Config
- Web Runtime Dependencies
- Group-Chat Privacy Tests
- Chat Conversation Engine
- Session Auth & Bridge Webhooks
- Sign-In Screen & Card Primitives
- TypeScript Node Compiler Config
- Photosynthesis Scanned Notes
- Operator CLI Commands
- QR & Pairing-Code Linking
- Multi-Tenancy Isolation Tests
- Digest Behaviour Tests
- Product Architecture Decisions
- Password Reset & Connection Tests
- Content-Hash Deduplication
- React & UI Package Dependencies
- System Topology & Shared Secret
- Reciprocal Rank Fusion
- Icon Sprite Sheet
- Accounts & Keys Schema
- Conversation & Key Endpoints
- shadcn Alert & Badge Variants
- Text Chunking
- Build Toolchain Dependencies
- Contribution Rules & Workstreams
- Classical IR Coursework Concepts
- Single-Command Launcher
- Extractor Routing
- Hero Illustration Design
- API Key Minting & Hashing
- Root npm Scripts
- Summarisation & Ingest Rationale
- Voice-Note Transcription
- OCR & PDF Extraction
- Core Document Schema
- Embedding & Fusion Decisions
- App Shell & Input Primitive
- Oxlint Rules
- Favicon Brand Mark
- Postgres & pgvector Deployment
- Ollama Embedding Client
- Chunk Persistence & tsvector
- Web npm Scripts
- TypeScript Project References
- Vite Build Configuration
- Internship Offer & BM25 Link
- DOCX Extraction
- Account Creation Flow
- Migration Runner Tests
- Package Root
- React Template Logo
- Vite Template Logo

## God Nodes (most connected - your core abstractions)
1. `get_conn()` - 62 edges
2. `cn()` - 55 edges
3. `compilerOptions` - 19 edges
4. `SearchResult` - 18 edges
5. `summarize()` - 16 edges
6. `OpenWAAdapter` - 15 edges
7. `_get()` - 15 edges
8. `compilerOptions` - 15 edges
9. `search()` - 14 edges
10. `react` - 14 edges

## Surprising Connections (you probably didn't know these)
- `Cosine Similarity with L2 Normalization` --semantically_similar_to--> `Ollama nomic-embed-text Embedder`  [INFERRED] [semantically similar]
  sample_docs/ir_lecture_notes.txt → README.md
- `Classical IR Modules Stay Library-Free` --conceptually_related_to--> `Classical Models Are Shared Work (viva coverage)`  [INFERRED]
  CONTRIBUTING.md → sample_docs/wadr_meeting_minutes.txt
- `Product Branch vs Coursework main Branch` --conceptually_related_to--> `Classical IR Modules Stay Library-Free`  [INFERRED]
  README.md → CONTRIBUTING.md
- `Decision: RRF Fusion with k=60, No Score Normalization` --rationale_for--> `Hybrid Search: BM25 + Dense Vectors Fused by RRF`  [INFERRED]
  sample_docs/wadr_meeting_minutes.txt → README.md
- `test_deleting_a_conversation_clears_its_messages()` --calls--> `get_conn()`  [EXTRACTED]
  tests/test_conversations.py → src/wadr/db.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **WADR End-to-End Ingest and Search Flow** — readme_whatsapp_bridge, readme_fastapi_api, readme_ingest_pipeline, readme_hybrid_search_rrf, readme_postgres_pgvector, readme_web_app [EXTRACTED 1.00]
- **Hand-Built Classical IR Machinery (viva evidence)** — sample_docs_ir_lecture_notes_boolean_model, sample_docs_ir_lecture_notes_tf_idf_weighting, sample_docs_ir_lecture_notes_inverted_index, contributing_classical_ir_library_free, sample_docs_wadr_meeting_minutes_classical_models_shared_work [INFERRED 0.85]
- **Digest and Summary Pipeline Design** — readme_weekly_digest, readme_digest_watermark_resume, readme_document_summaries, readme_ocr_rubble_word_length_heuristic, readme_summaries_never_during_ingest [EXTRACTED 1.00]
- **Photosynthesis Two-Stage Pipeline: light reactions yield ATP/NADPH that power the Calvin cycle** — sample_docs_scanned_notes_light_dependent_reactions, sample_docs_scanned_notes_atp, sample_docs_scanned_notes_nadph, sample_docs_scanned_notes_calvin_cycle, sample_docs_scanned_notes_two_stage_energy_conversion [INFERRED 0.85]
- **Chloroplast Compartmentalization: thylakoid membranes and stroma host distinct reaction stages** — sample_docs_scanned_notes_chloroplast, sample_docs_scanned_notes_thylakoid_membranes, sample_docs_scanned_notes_stroma, sample_docs_scanned_notes_exam_tip_draw_diagram_first [INFERRED 0.75]
- **Exploded Isometric Stack Motif (two slabs joined by dashed guides)** — web_src_assets_hero_wireframe_upper_slab, web_src_assets_hero_gradient_lower_slab, web_src_assets_hero_dashed_alignment_guides, web_src_assets_hero_exploded_view_composition [EXTRACTED 1.00]
- **Social Community Footer Link Row** — web_public_icons_bluesky_icon, web_public_icons_discord_icon, web_public_icons_x_icon, web_public_icons_github_icon [INFERRED 0.85]
- **Accent Stroke UI Icon Family** — web_public_icons_documentation_icon, web_public_icons_social_icon, web_public_icons_brand_accent_color [EXTRACTED 1.00]

## Communities (66 total, 4 thin omitted)

### Community 0 - "Database Layer & Value Objects"
Cohesion: 0.07
Nodes (52): account_ids(), Connection, Format a float list as a pgvector literal; pair with a ::vector cast in SQL.…, to_vector(), Shared value objects. Keep this import-light: engine and adapters both use it., Human 'who + when' suffix for display; '' when unknown., SearchResult, _normalize() (+44 more)

### Community 1 - "Weekly Digest Pipeline"
Cohesion: 0.06
Nodes (46): parametrize, Internal FastAPI app. /search works; the rest are workstream stubs., _arrivals(), build(), compose(), _delivery(), Connection, datetime (+38 more)

### Community 2 - "MCP Agent Server"
Cohesion: 0.09
Nodes (26): WADR - WhatsApp Document Retrieval. See README.md and TODO.md., find_similar(), MCP server: hand an agent your WhatsApp document archive. Run it over stdio and…, Resolve the API key once per call, so a revoked key stops working immediately…, read_document(), recent_documents(), search_documents(), _user() (+18 more)

### Community 3 - "Chat Search UI"
Cohesion: 0.12
Nodes (20): lucide-react, sonner, ChatView(), EXAMPLES, ResultCard(), ConversationList(), Button(), buttonVariants (+12 more)

### Community 4 - "shadcn Avatar & Menu Primitives"
Cohesion: 0.12
Nodes (18): Avatar(), AvatarBadge(), AvatarFallback(), AvatarGroup(), AvatarGroupCount(), AvatarImage(), DropdownMenuCheckboxItem(), DropdownMenuContent() (+10 more)

### Community 5 - "WhatsApp Bridge (Baileys)"
Cohesion: 0.09
Nodes (23): AUTH_ROOT, {
  default: makeWASocket,
  useMultiFileAuthState,
  downloadMediaMessage,
  fetchLatestBaileysVersion,
  DisconnectReason,
  Browsers,
}, fs, http, json(), onMessage(), path, postWadr() (+15 more)

### Community 6 - "Number Linking & API Key Dialogs"
Cohesion: 0.13
Nodes (14): ApiKeysDialog(), LinkDialog(), NumbersDialog(), NumbersPanel(), STATUS, Dialog(), DialogContent(), DialogDescription() (+6 more)

### Community 7 - "Password Hashing & Sessions"
Cohesion: 0.17
Nodes (21): AuthError, delete_account(), hash_password(), list_accounts(), log_in(), log_out(), mark_linked(), _new_session() (+13 more)

### Community 8 - "shadcn Component Registry Config"
Cohesion: 0.09
Nodes (21): aliases, components, hooks, lib, ui, utils, iconLibrary, menuAccent (+13 more)

### Community 9 - "Adapter Contract (Inward Dependency)"
Cohesion: 0.11
Nodes (12): ABC, MessagingInterface, datetime, Adapter contract. HARD RULE: dependency points inward only - the engine…, A messaging channel that hands documents in and carries results out., Inbound document -> ingestion pipeline. Returns document id, or None if skipped., A newly ingested document matched a saved search. Default: do nothing - the…, Deliver search results back over this channel. (+4 more)

### Community 10 - "Document Download & Account Routes"
Cohesion: 0.11
Nodes (20): FileResponse, download(), get_accounts(), get_keys(), me(), no_build(), The file itself. inline=1 for previewing it in the page instead of saving. A…, similar() (+12 more)

### Community 11 - "WhatsApp Command Handling (/find, /get)"
Cohesion: 0.17
Nodes (12): account_for_session_key(), _key(), OpenWAAdapter, WhatsApp adapter. The Node bridge (bridge/) owns every WhatsApp session - one…, A '/get <n>' message: send back the nth file from the last /find., Who is asking, for search scoping - or None when it is the owner. A linked…, The bridge reported a session_key with no linked number behind it., Validate + decode an inbound bridge payload, delegate to on_document(). (+4 more)

### Community 12 - "TypeScript App Compiler Config"
Cohesion: 0.10
Nodes (20): compilerOptions, allowArbitraryExtensions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection (+12 more)

### Community 13 - "Web Runtime Dependencies"
Cohesion: 0.11
Nodes (18): @base-ui/react, clsx, @fontsource-variable/geist, next-themes, oxlint, react-dom, shadcn, tailwind-merge (+10 more)

### Community 14 - "Group-Chat Privacy Tests"
Cohesion: 0.14
Nodes (14): Messaging adapters. HARD RULE: the engine never imports this package., _found(), linked(), fixture, A linked number sits in group chats full of other people, and anyone can type…, Exact equality, not ILIKE: a prefix of someone's number is not them., Two people searching in one group must not renumber each other., One linked number holding a private document and a group document. (+6 more)

### Community 15 - "Chat Conversation Engine"
Cohesion: 0.17
Nodes (16): get_history(), post_message(), answer(), _found(), history(), _nothing_found(), NotYours, _own() (+8 more)

### Community 16 - "Session Auth & Bridge Webhooks"
Cohesion: 0.15
Nodes (17): post, Response, Resolve a session token to {id, email}, or None if absent/expired., user_for_token(), bridge_document(), bridge_get(), bridge_query(), bridge_status() (+9 more)

### Community 17 - "Sign-In Screen & Card Primitives"
Cohesion: 0.19
Nodes (13): AuthScreen(), Card(), CardAction(), CardContent(), CardDescription(), CardFooter(), CardHeader(), CardTitle() (+5 more)

### Community 18 - "TypeScript Node Compiler Config"
Cohesion: 0.12
Nodes (16): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, noEmit, noFallthroughCasesInSwitch (+8 more)

### Community 19 - "Photosynthesis Scanned Notes"
Cohesion: 0.22
Nodes (14): ATP, Biology - Photosynthesis Revision (Scanned Study Notes), Calvin Cycle, Carbon Dioxide (fixation input), Chloroplast, Exam Tip: Draw the Chloroplast Diagram Before Writing the Answer (worth two marks), Glucose (reading truncated at page edge), Light-Dependent Reactions (+6 more)

### Community 20 - "Operator CLI Commands"
Cohesion: 0.19
Nodes (12): emails(), Every registered address - for an operator who forgot which they used., main(), wadr command-line entry point - operator tasks only. The product surface is the…, Digest every user with a connected number. Returns {user_id: text} sent., send_all(), main(), migrate() (+4 more)

### Community 21 - "QR & Pairing-Code Linking"
Cohesion: 0.22
Nodes (13): account_pair(), account_qr(), _own_account(), Poll while linking: {status, qr, pairing_code, phone}., Pairing code instead of a QR - iPhones scan screen QRs badly., _call(), pairing_code(), Talking to the Node bridge, which owns every WhatsApp session. One bridge… (+5 more)

### Community 22 - "Multi-Tenancy Isolation Tests"
Cohesion: 0.14
Nodes (7): Indexing: Ollama embeddings, tsvector persistence, from-scratch inverted index…, fixture, Tenancy is the security boundary of this product: a document must be reachable…, Two users, one linked number each, one private document each., Dense retrieval always returns its nearest k; the reply must not call that a…, test_a_miss_is_reported_as_a_guess_not_a_match(), world()

### Community 23 - "Digest Behaviour Tests"
Cohesion: 0.14
Nodes (9): fixture, The weekly digest: what arrived, to whom, and only once., A linked number with one freshly received document., A filename like wa-1788370118.jpeg says nothing on its own., WhatsApp timestamps come from the sender's phone, whose clock may be ahead of…, test_a_document_timestamped_in_the_future_is_not_repeated(), test_a_user_with_nothing_new_gets_no_message(), test_each_file_carries_a_summary_of_what_it_is() (+1 more)

### Community 24 - "Product Architecture Decisions"
Cohesion: 0.18
Nodes (13): Account-Scoped SHA-256 Hashed API Keys, /find and /get WhatsApp Commands, Group-Chat Visibility Rule (asker-scoped /find and /get), Hybrid Search: BM25 + Dense Vectors Fused by RRF, "Loose Match" Labelling Instead of Score Thresholding, WADR MCP Server (4 tools), Product Branch vs Coursework main Branch, Single Scoping Point in retrieval/service.py (+5 more)

### Community 25 - "Password Reset & Connection Tests"
Cohesion: 0.15
Nodes (7): Postgres connection layer. One env var, one function., account(), fixture, Passwords are one-way hashes, so the recovery path is replacement., Salted: identical passwords must not produce identical hashes., test_the_plaintext_is_never_stored(), test_two_accounts_with_one_password_get_different_hashes()

### Community 26 - "Content-Hash Deduplication"
Cohesion: 0.23
Nodes (12): add_sighting(), file_hash(), find_document(), insert_document(), Connection, datetime, Content-hash dedupe: the same file forwarded around = one document, many…, SHA-256 hex digest - the identity of a document. (+4 more)

### Community 27 - "React & UI Package Dependencies"
Cohesion: 0.15
Nodes (13): dependencies, @base-ui/react, class-variance-authority, clsx, @fontsource-variable/geist, lucide-react, next-themes, react (+5 more)

### Community 28 - "System Topology & Shared Secret"
Cohesion: 0.23
Nodes (12): WADR_BRIDGE_TOKEN Shared Secret, FastAPI Application (wadr.api.app), Coupled Process Lifecycle (one dies, both stop), Salted scrypt Password Hashes + CLI Reset, WADR — Search Your WhatsApp Documents, Web App (React + shadcn chat UI), WhatsApp Bridge (Node, Baileys, N sessions), /src/main.tsx Module Entry Point (+4 more)

### Community 29 - "Reciprocal Rank Fusion"
Cohesion: 0.24
Nodes (10): datetime, Reciprocal Rank Fusion: combine ranked lists whose scores aren't comparable., Fuse ranked lists of ids (any hashable): score(d) = sum over lists containing d…, Re-rank so recently shared documents score higher: score(d) *= 1 + weight * 0.5…, recency_boost(), rrf(), test_default_k_is_60(), test_item_in_both_lists_outranks_single_list_items() (+2 more)

### Community 30 - "Icon Sprite Sheet"
Cohesion: 0.33
Nodes (12): Bluesky Icon, Purple Brand Accent aa3bff, Developer Resources Affordance, Discord Icon, Documentation Icon, External Community Link Affordance, GitHub Icon, Near Black Glyph Fill 08060d (+4 more)

### Community 31 - "Accounts & Keys Schema"
Cohesion: 0.24
Nodes (7): chat_messages, sessions, users, whatsapp_accounts, api_keys, digest_runs, conversations

### Community 32 - "Conversation & Key Endpoints"
Cohesion: 0.25
Nodes (9): drop_conversation(), get_conversations(), Product HTTP API. Run: uv run uvicorn wadr.api.app:app --reload Everything…, remove_account(), remove_key(), conversations(), delete(), Newest first. The title is the first thing the user asked in it. (+1 more)

### Community 33 - "shadcn Alert & Badge Variants"
Cohesion: 0.24
Nodes (8): class-variance-authority, Alert(), AlertAction(), AlertDescription(), AlertTitle(), alertVariants, Badge(), badgeVariants

### Community 34 - "Text Chunking"
Cohesion: 0.31
Nodes (8): chunk(), Split extracted text into overlapping chunks for embedding + lexical indexing., Sliding character window; each cut snaps back to the last space so words stay…, test_consecutive_chunks_overlap(), test_empty_text_gives_no_chunks(), test_giant_unbroken_token_is_hard_cut(), test_long_text_respects_size_and_keeps_every_word(), test_short_text_is_one_chunk()

### Community 35 - "Build Toolchain Dependencies"
Cohesion: 0.20
Nodes (10): devDependencies, oxlint, tailwindcss, @tailwindcss/vite, @types/node, @types/react, @types/react-dom, typescript (+2 more)

### Community 36 - "Contribution Rules & Workstreams"
Cohesion: 0.22
Nodes (9): Branch Naming Convention (ws<N>/<kebab>), Engine Never Imports Adapters (inward-only dependency rule), main Stays Green (pytest + ruff), Append-Only Numbered Migrations, Pull Request Workflow, TODO.md Checklist / Unskip-Test Gate, Classical Models Are Shared Work (viva coverage), Decision: Thin Node Bridge, Retrieval Behind a Python Interface (+1 more)

### Community 37 - "Classical IR Coursework Concepts"
Cohesion: 0.31
Nodes (9): Classical IR Modules Stay Library-Free, CS4021 Information Retrieval Exam, Autumn 2026 End-Semester Exam Timetable (CSE Sem 7), Hall Tickets and Attendance Condonation Rules, Boolean Retrieval Model, CS4021 IR Lecture 7 Notes, Inverted Index and Posting Lists, TF-IDF Term Weighting (+1 more)

### Community 38 - "Single-Command Launcher"
Cohesion: 0.25
Nodes (8): children, crypto, ENV_FILE, fs, path, ROOT, { spawn, spawnSync }, stop()

### Community 39 - "Extractor Routing"
Cohesion: 0.22
Nodes (5): Extractors: pure functions `bytes -> str` for text, pdf, docx, images (OCR) and…, Plain text / markdown passthrough., Ingestion entry point: extension -> extractor -> dedupe -> chunk -> index. This…, (chat_id, query_text) for every saved search this document satisfies. Uses the…, _standing_matches()

### Community 40 - "Hero Illustration Design"
Cohesion: 0.33
Nodes (9): Dashed Vertical Alignment Guides, Exploded-View Isometric Composition, Solid Lower Slab with Violet Gradient Edge, Hero Isometric Layered Slab Illustration, Layered System / Stacked Architecture Metaphor, Marketing Hero Visual Role, Minimal Light Aesthetic (Transparent Background, Thin Line Work), Violet/Purple Brand Accent Color (+1 more)

### Community 41 - "API Key Minting & Hashing"
Cohesion: 0.25
Nodes (8): create_api_key(), _key_hash(), list_api_keys(), Mint a key. Returned in full exactly once - only its hash is stored., Resolve a key to {id, email}, or None. Also stamps last_used_at., user_for_api_key(), add_key(), Mint a key. The plaintext is in this response and nowhere else, ever.

### Community 42 - "Root npm Scripts"
Cohesion: 0.29
Nodes (6): description, name, private, scripts, setup, start

### Community 43 - "Summarisation & Ingest Rationale"
Cohesion: 0.33
Nodes (7): Digest Resumes From Last Watermark, Not "7 Days Ago", One-Line Document Summaries (wadr summarize), Ingest Pipeline: extract -> dedupe -> chunk -> embed, Tesseract OCR + faster-whisper Voice-Note Extraction, OCR Rubble Detection via Mean Word Length < 3.5, Summaries Written On First Use, Never During Ingest, Weekly Digest (wadr digest)

### Community 44 - "Voice-Note Transcription"
Cohesion: 0.33
Nodes (6): extract(), _get_model(), Speech-to-text for WhatsApp voice notes (.ogg/.opus/.m4a) via faster-whisper.…, Load the model once per process; later calls reuse it., Transcribe a voice note to text. faster-whisper accepts a BinaryIO directly -…, WhisperModel

### Community 45 - "OCR & PDF Extraction"
Cohesion: 0.33
Nodes (5): extract(), OCR for images (and scanned PDF pages routed from pdf.py). Needs the tesseract…, OCR printed text out of an image (png/jpg) via pytesseract + Pillow., extract(), PDF text extraction via PyMuPDF, with OCR fallback for scanned pages.

### Community 46 - "Core Document Schema"
Cohesion: 0.53
Nodes (5): chunks, documents, feedback, sightings, standing_queries

### Community 47 - "Embedding & Fusion Decisions"
Cohesion: 0.33
Nodes (6): 127.0.0.1 Defaults Instead of localhost (Happy Eyeballs stall), Ollama nomic-embed-text Embedder, Cosine Similarity with L2 Normalization, WADR Meeting Minutes, 8 July 2026, Decision: nomic-embed-text on Ollama + Postgres/pgvector, Decision: RRF Fusion with k=60, No Score Normalization

### Community 48 - "App Shell & Input Primitive"
Cohesion: 0.33
Nodes (3): react, App(), Input()

### Community 49 - "Oxlint Rules"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 50 - "Favicon Brand Mark"
Cohesion: 0.53
Nodes (6): Favicon Brand Mark, Downward Lightning Bolt Glyph, Masked Blurred-Ellipse Glow Treatment, Speed / Instant-Energy Product Identity Signal, Violet Brand Palette, Web App Browser Tab Icon Asset

### Community 51 - "Postgres & pgvector Deployment"
Cohesion: 0.50
Nodes (5): db Service (pgvector/pgvector:pg16), Host Port 5433 Mapping, wadr_pgdata Named Volume, Numbered SQL Migrations + schema_migrations, PostgreSQL 16 + pgvector Store

### Community 52 - "Ollama Embedding Client"
Cohesion: 0.50
Nodes (4): embed(), embed_query(), Ollama embedding client (nomic-embed-text, 768 dims). ponytail: urllib instead…, Batch-embed texts. Returns None when Ollama is unreachable - callers degrade…

### Community 53 - "Chunk Persistence & tsvector"
Cohesion: 0.40
Nodes (4): index_chunks(), Connection, Chunk persistence: text + tsvector (+ embedding when available) into Postgres., Upsert chunk rows. tsv is computed in-database; embedding may be NULL (Ollama…

### Community 54 - "Web npm Scripts"
Cohesion: 0.40
Nodes (5): scripts, build, dev, lint, preview

### Community 55 - "TypeScript Project References"
Cohesion: 0.40
Nodes (4): compilerOptions, paths, files, references

### Community 56 - "Vite Build Configuration"
Cohesion: 0.50
Nodes (3): @tailwindcss/vite, vite, @vitejs/plugin-react

### Community 57 - "Internship Offer & BM25 Link"
Cohesion: 0.50
Nodes (4): Nimbus Systems Internship Offer Letter, Nimbus Systems Private Limited, Search Infrastructure Intern Role (query understanding, ranking), BM25 Probabilistic Ranking

### Community 58 - "DOCX Extraction"
Cohesion: 0.50
Nodes (3): extract(), DOCX text extraction via python-docx., Extract plain text from a .docx: paragraph text, then table cell text.

### Community 59 - "Account Creation Flow"
Cohesion: 0.67
Nodes (3): create_account(), Reserve a slot for a new number. The bridge starts a WhatsApp session named…, add_account()

## Ambiguous Edges - Review These
- `Search Filter Tokens (from:/in:/type:/before:/after:)` → `Ammi's Hyderabadi Chicken Biryani Recipe`  [AMBIGUOUS]
  sample_docs/hyderabadi_biryani_recipe.txt · relation: conceptually_related_to
- `Light-Dependent Reactions` → `Thylakoid Membranes (reading truncated at page edge)`  [AMBIGUOUS]
  sample_docs/scanned_notes.png · relation: references
- `Calvin Cycle` → `Glucose (reading truncated at page edge)`  [AMBIGUOUS]
  sample_docs/scanned_notes.png · relation: references
- `Layered System / Stacked Architecture Metaphor` → `Marketing Hero Visual Role`  [AMBIGUOUS]
  web/src/assets/hero.png · relation: rationale_for
- `Icon Sprite Sheet` → `Purple Brand Accent aa3bff`  [AMBIGUOUS]
  web/public/icons.svg · relation: conceptually_related_to
- `Violet Brand Palette` → `Speed / Instant-Energy Product Identity Signal`  [AMBIGUOUS]
  web/public/favicon.svg · relation: conceptually_related_to

## Knowledge Gaps
- **137 isolated node(s):** `http`, `path`, `fs`, `{
  default: makeWASocket,
  useMultiFileAuthState,
  downloadMediaMessage,
  fetchLatestBaileysVersion,
  DisconnectReason,
  Browsers,
}`, `QRCode` (+132 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 355 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Search Filter Tokens (from:/in:/type:/before:/after:)` and `Ammi's Hyderabadi Chicken Biryani Recipe`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Light-Dependent Reactions` and `Thylakoid Membranes (reading truncated at page edge)`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `Calvin Cycle` and `Glucose (reading truncated at page edge)`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `Layered System / Stacked Architecture Metaphor` and `Marketing Hero Visual Role`?**
  _Edge tagged AMBIGUOUS (relation: rationale_for) - confidence is low._
- **What is the exact relationship between `Icon Sprite Sheet` and `Purple Brand Accent aa3bff`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Violet Brand Palette` and `Speed / Instant-Energy Product Identity Signal`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `get_conn()` connect `Password Hashing & Sessions` to `Conversation & Key Endpoints`, `Weekly Digest Pipeline`, `Database Layer & Value Objects`, `MCP Agent Server`, `Extractor Routing`, `API Key Minting & Hashing`, `WhatsApp Command Handling (/find, /get)`, `Group-Chat Privacy Tests`, `Chat Conversation Engine`, `Session Auth & Bridge Webhooks`, `Operator CLI Commands`, `Multi-Tenancy Isolation Tests`, `Digest Behaviour Tests`, `Password Reset & Connection Tests`, `Content-Hash Deduplication`, `Account Creation Flow`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._