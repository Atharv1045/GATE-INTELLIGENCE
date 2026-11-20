"""
RAG-Based AI Tutor Engine for GATE Intelligence (Agent 6).
Features:
- Deterministic & Extensible Intent Classifier (conceptual | pyq_search | specific_question | hybrid)
- Explicit Negative Retrieval Constraint Detection ("do not search question bank", "conceptually only")
- Direct Exact Question Lookup (e.g. "Solve GATE CS 2012 Question 32") without false substitution
- Calibrated Retrieval Relevance Guard (rejects irrelevant noise candidates below threshold)
- Curated High-Pedagogy Offline Knowledge Base for Core GATE Concepts (Deadlock, Semaphore, Paging, Dijkstra, etc.)
- Strict Provenance Separation (conceptual_explanation vs official_key vs manually_verified vs ai_generated vs unverified)
- Intent-Aware Gemini Dynamic Prompting with Graceful Offline Fallback
"""
from __future__ import annotations

import json
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.security import sanitize_untrusted_pdf_text
from app.ml.embedding_service import LazyEmbeddingService


def classify_tutor_intent(query: str) -> Dict[str, Any]:
    """
    Deterministic intent and entity classifier for AI Tutor queries.
    Returns:
        intent: 'conceptual' | 'pyq_search' | 'specific_question' | 'hybrid'
        negative_retrieval: bool
        question_number: Optional[int]
        year: Optional[int]
        paper_code: Optional[str]
        cleaned_query: str
    """
    q_lower = query.lower().strip()

    # 1. Detect explicit negative retrieval constraint
    neg_patterns = [
        r"\b(?:do\s+not|don'?t|never|no)\s+(?:search|retrieve|look\s*up|fetch|include|show|use)\s+(?:the\s+)?(?:question\s*bank|questions?|pyqs?|previous\s*year)\b",
        r"\bwithout\s+(?:retrieving|searching|pyqs?|questions?|previous\s*year)\b",
        r"\b(?:conceptually\s+only|purely\s+conceptual(?:ly)?|only\s+explain\s+concept(?:ually)?|in\s+theory\s+only)\b",
        r"\bdo\s+not\s+retrieve\s+previous-?year\s+questions\b",
    ]
    negative_retrieval = any(re.search(pat, q_lower) for pat in neg_patterns)

    # 2. Extract Entities (Question Number, Year, Paper Code)
    q_num_match = re.search(r"\b(?:q(?:uestion)?\.?\s*(\d+)|question\s*number\s*(\d+))\b", q_lower)
    question_number = None
    if q_num_match:
        question_number = int(q_num_match.group(1) or q_num_match.group(2))

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", q_lower)
    year = int(year_match.group(1)) if year_match else None

    paper_match = re.search(r"\bgate\s+([a-z]{2})\b", q_lower)
    paper_code = paper_match.group(1).upper() if paper_match else None

    # Cleaned query (remove negative phrases and instruction wrappers)
    clean_q = query
    for pat in neg_patterns:
        clean_q = re.sub(pat, "", clean_q, flags=re.IGNORECASE)
    clean_q = re.sub(r"\s+", " ", clean_q).strip()

    # 3. Specific Question Lookup Intent
    if question_number is not None and not negative_retrieval:
        if re.search(r"\b(solve|solution|answer|explain\s+question|what\s+is\s+q|q\.\d+)\b", q_lower) or "question" in q_lower:
            return {
                "intent": "specific_question",
                "negative_retrieval": False,
                "question_number": question_number,
                "year": year,
                "paper_code": paper_code,
                "cleaned_query": clean_q,
            }

    # 4. Negative Retrieval forces pure conceptual explanation
    if negative_retrieval:
        return {
            "intent": "conceptual",
            "negative_retrieval": True,
            "question_number": None,
            "year": year,
            "paper_code": paper_code,
            "cleaned_query": clean_q,
        }

    # 5. Hybrid Intent: requests both conceptual explanation AND PYQs
    hybrid_patterns = [
        r"\b(?:explain|what\s+is|concept).+?\band\s+(?:then\s+)?(?:find|show|give|retrieve|solve|look\s*up)\s+(?:related\s+)?(?:gate\s+)?(?:pyqs?|questions?)\b",
        r"\b(?:find|show|give)\s+(?:related\s+)?(?:gate\s+)?(?:pyqs?|questions?).+?\band\s+(?:explain|teach)\b",
        r"\bwith\s+(?:related\s+)?(?:gate\s+)?(?:pyqs?|questions?|examples\s+from\s+pyqs?)\b",
        r"\balong\s+with\s+(?:gate\s+)?(?:pyqs?|questions?)\b",
    ]
    if any(re.search(pat, q_lower) for pat in hybrid_patterns):
        return {
            "intent": "hybrid",
            "negative_retrieval": False,
            "question_number": question_number,
            "year": year,
            "paper_code": paper_code,
            "cleaned_query": clean_q,
        }

    # 6. PYQ Search Intent: explicitly asking to find/show/search previous-year questions
    pyq_patterns = [
        r"\b(?:find|search|show|get|list|give\s+me)\s+(?:all\s+)?(?:previous\s*year|past\s*year|gate\s+)?(?:questions?|pyqs?|problems?)\b",
        r"\b(?:questions?|pyqs?|problems?)\s+(?:on|about|for|related\s+to)\b",
        r"\bgate\s+(?:[a-z]{2}\s+)?questions?\b",
        r"\bprevious\s*year\s*questions?\b",
        r"\bpyqs?\s+(?:on|of|for|about)\b",
    ]
    if any(re.search(pat, q_lower) for pat in pyq_patterns):
        return {
            "intent": "pyq_search",
            "negative_retrieval": False,
            "question_number": question_number,
            "year": year,
            "paper_code": paper_code,
            "cleaned_query": clean_q,
        }

    # 7. Conceptual Intent: triggers on conceptual interrogatives or definitions
    concept_triggers = [
        r"\b(explain|what\s+is|what\s+are|how\s+does|how\s+do|how\s+to|describe|define|concept\s+of|difference\s+between|why\s+do|when\s+does|compare|tutorial|example\s+of)\b"
    ]
    if any(re.search(pat, q_lower) for pat in concept_triggers):
        return {
            "intent": "conceptual",
            "negative_retrieval": False,
            "question_number": question_number,
            "year": year,
            "paper_code": paper_code,
            "cleaned_query": clean_q,
        }

    # Default fallback: keyword searches without explanation trigger default to pyq_search
    return {
        "intent": "pyq_search",
        "negative_retrieval": False,
        "question_number": question_number,
        "year": year,
        "paper_code": paper_code,
        "cleaned_query": clean_q,
    }


def is_retrieval_relevant(combined_score: float, tfidf_sim: float, emb_sim: float) -> bool:
    """
    Calibrated Relevance Guard:
    Ensures that questions returned have genuine lexical keyword match (TF-IDF >= 0.08)
    or strong semantic vector match (emb_sim >= 0.48), eliminating noise candidates.
    """
    if tfidf_sim >= 0.08:
        return True
    if emb_sim >= 0.48:
        return True
    if combined_score >= 0.28 and (tfidf_sim >= 0.03 or emb_sim >= 0.38):
        return True
    return False


OFFLINE_CONCEPT_KNOWLEDGE_BASE: Dict[str, Dict[str, Any]] = {
    "deadlock": {
        "keywords": ["deadlock", "deadlocks", "banker's algorithm", "resource allocation graph", "circular wait", "safe state"],
        "title": "Deadlock in Operating Systems",
        "markdown": (
            "### 1. Definition & Core Concept\n"
            "A **Deadlock** in an Operating System is a permanent blocking situation where a set of processes are unable to proceed "
            "because each process holds at least one resource and is waiting to acquire another resource currently held by another process in the same set.\n\n"
            "### 2. How It Works (Coffman's 4 Necessary Conditions)\n"
            "A deadlock can arise if and only if all four **Coffman conditions** hold simultaneously:\n"
            "1. **Mutual Exclusion:** At least one resource must be non-shareable (only one process can use it at a time).\n"
            "2. **Hold and Wait:** A process must currently hold at least one resource while waiting to acquire additional resources held by other processes.\n"
            "3. **No Preemption:** Resources cannot be forcibly taken from a process; they can only be released voluntarily after the process completes its task.\n"
            "4. **Circular Wait:** A closed chain of processes exists: $P_0$ waits for a resource held by $P_1$, $P_1$ waits for $P_2$, ..., and $P_n$ waits for $P_0$.\n\n"
            "### 3. Clear, Intuitive Example\n"
            "Consider two processes $P_1$ and $P_2$, and two resources $R_1$ (Tape Drive) and $R_2$ (Printer):\n"
            "- Step 1: $P_1$ requests and acquires $R_1$.\n"
            "- Step 2: $P_2$ requests and acquires $R_2$.\n"
            "- Step 3: $P_1$ now requests $R_2$ (it is blocked because $P_2$ holds $R_2$).\n"
            "- Step 4: $P_2$ now requests $R_1$ (it is blocked because $P_1$ holds $R_1$).\n"
            "Both $P_1$ and $P_2$ are indefinitely waiting for each other. Neither can proceed, resulting in a **deadlock**.\n\n"
            "### 4. Key Properties & Deadlock Handling Strategies\n"
            "- **Resource Allocation Graph (RAG):**\n"
            "  * If a graph has **no cycles**, deadlock is **impossible**.\n"
            "  * If resources have a **single instance**, a cycle is **necessary and sufficient** for deadlock.\n"
            "  * If resources have **multiple instances**, a cycle is **necessary but not sufficient**.\n"
            "- **Handling Methods:**\n"
            "  1. *Deadlock Prevention:* Invalidate at least one of the 4 Coffman conditions (e.g., impose global resource ordering to break Circular Wait).\n"
            "  2. *Deadlock Avoidance:* Dynamically ensure the system remains in a **Safe State** using **Dijkstra's Banker's Algorithm** ($O(m \\cdot n^2)$).\n"
            "  3. *Deadlock Detection & Recovery:* Periodically run a cycle detection algorithm and recover via process termination or resource preemption.\n"
            "  4. *Ostrich Algorithm:* Ignore the problem (used by most general-purpose OS like Linux and Windows for performance).\n\n"
            "### 5. GATE Exam Takeaways\n"
            "- **Cycle Rule:** In multi-instance RAGs, always simulate reduction/allocation to check if processes can complete; never conclude deadlock simply by spotting a cycle!\n"
            "- **Starvation vs. Deadlock:** In starvation, a process waits indefinitely due to unfair scheduling, but other processes make progress. In deadlock, NO process in the set can make progress."
        ),
    },
    "semaphore": {
        "keywords": ["semaphore", "semaphores", "binary semaphore", "counting semaphore", "mutex", "wait and signal", "p and v"],
        "title": "Semaphores in Operating Systems",
        "markdown": (
            "### 1. Definition & Core Concept\n"
            "A **Semaphore** (introduced by Edsger Dijkstra) is a protected synchronization variable used to coordinate concurrent processes "
            "and solve the Critical Section Problem. It is an integer variable accessed exclusively through two atomic, indivisible operations: "
            "`wait()` (historically called $P$ or Dutch *proberen*) and `signal()` (historically called $V$ or Dutch *verhogen*).\n\n"
            "### 2. How It Works (Binary vs. Counting Semaphores)\n"
            "#### A. Binary Semaphore (Mutex)\n"
            "- Value is restricted strictly to **0 or 1**.\n"
            "- Initialized to `1` to provide mutual exclusion for a shared critical resource.\n"
            "- Only one process can enter the Critical Section at any time.\n\n"
            "#### B. Counting Semaphore\n"
            "- Value can take any non-negative integer over an unrestricted domain $[0, N]$.\n"
            "- Initialized to $N$ representing the number of available instances of a shared resource.\n"
            "- Tracks available resources: each `wait()` decrements the counter; each `signal()` increments it.\n\n"
            "#### Core Atomic Operations (Non-Busy Waiting / Block & Wakeup Implementation):\n"
            "```c\n"
            "void wait(Semaphore S) {\n"
            "    S.value--;\n"
            "    if (S.value < 0) {\n"
            "        // add this process to S.waiting_queue\n"
            "        block();\n"
            "    }\n"
            "}\n\n"
            "void signal(Semaphore S) {\n"
            "    S.value++;\n"
            "    if (S.value <= 0) {\n"
            "        // remove a process P from S.waiting_queue\n"
            "        wakeup(P);\n"
            "    }\n"
            "}\n"
            "```\n\n"
            "### 3. Clear, Intuitive Example (Critical Section Mutual Exclusion)\n"
            "```c\n"
            "Semaphore mutex = 1;\n\n"
            "void Process_A() {\n"
            "    wait(mutex);      // mutex becomes 0; Process_A enters\n"
            "    /* Critical Section: update bank account balance */\n"
            "    signal(mutex);    // mutex becomes 1; other processes can now enter\n"
            "}\n"
            "```\n"
            "If Process $B$ calls `wait(mutex)` while Process $A$ is in the Critical Section, `mutex` decrements to `0 - 1 = -1`. "
            "Process $B$ is blocked and put into the semaphore's queue until Process $A$ executes `signal(mutex)`.\n\n"
            "### 4. Key Properties & Queue Interpretation\n"
            "- **Value >= 0:** Represents the number of processes that can execute `wait()` without blocking.\n"
            "- **Value < 0:** The absolute value $|S.value|$ equals the exact number of processes currently blocked in the semaphore queue!\n"
            "- **Atomicity:** `wait()` and `signal()` must execute without interruption (hardware test-and-set or disabling interrupts in kernel mode).\n\n"
            "### 5. GATE Exam Takeaways & Standard Formula\n"
            "- **Formula:** If a counting semaphore is initialized to $k$, and undergoes $m$ `wait()` operations and $n$ `signal()` operations, "
            "its final value is:\n"
            "  $$\\text{Final Value} = k - m + n$$\n"
            "- If $\\text{Final Value} < 0$, the number of blocked processes is $|k - m + n|$."
        ),
    },
    "paging": {
        "keywords": ["paging", "page table", "tlb", "virtual memory", "page fault", "page replacement", "effective memory access time", "emat", "framing"],
        "title": "Paging & Virtual Memory in Operating Systems",
        "markdown": (
            "### 1. Definition & Core Concept\n"
            "**Paging** is a memory-management scheme that permits the physical address space of a process to be non-contiguous. "
            "It eliminates external fragmentation by partitioning physical memory into fixed-sized blocks called **Frames** and logical memory "
            "into blocks of the exact same size called **Pages**.\n\n"
            "### 2. How It Works (Address Translation & Hardware Mechanism)\n"
            "1. **Logical Address Structure:** The CPU generates a logical address split into two parts:\n"
            "   - **Page Number ($p$):** Used as an index into the process's Page Table.\n"
            "   - **Page Offset ($d$):** Combined with the base frame address to identify the exact byte in memory.\n"
            "2. **Page Table:** Maps each logical Page Number $p$ to a physical Frame Number $f$.\n"
            "3. **Physical Address:** Formed as $(f \\times \\text{Frame Size}) + d$.\n"
            "4. **TLB (Translation Lookaside Buffer):** High-speed associative hardware cache. Checks $p$ in parallel: on TLB Hit, "
            "frame number $f$ is retrieved in 1-2 ns without accessing main memory.\n\n"
            "### 3. Clear, Intuitive Example\n"
            "Consider a 32-bit Logical Address space with a **4 KB ($2^{12}$ Bytes)** Page Size:\n"
            "- Offset $d = 12$ bits (since $2^{12} = 4096$).\n"
            "- Page Number $p = 32 - 12 = 20$ bits ($2^{20} = 1,048,576$ pages).\n"
            "- If Logical Address is `0x00003A14`:\n"
            "  * $p = 3$, $d = \\text{0xA14}$.\n"
            "  * Page Table entry 3 holds Frame Number `7`.\n"
            "  * Physical Address becomes Frame `7` at offset `0xA14`.\n\n"
            "### 4. Key Properties & Fragmentation Analysis\n"
            "- **External Fragmentation:** Zero (any free frame can be allocated to any process).\n"
            "- **Internal Fragmentation:** Present only on the last page of a process (on average, half a page size per process).\n"
            "- **Page Fault:** Occurs when the CPU references a page whose Valid/Invalid bit in the Page Table is set to 0 (page not resident in physical RAM).\n\n"
            "### 5. GATE Exam Takeaways & Standard Formulae\n"
            "- **Effective Memory Access Time (EMAT):**\n"
            "  With TLB hit ratio $h$, TLB access time $t_{tlb}$, and Main Memory access time $t_{mem}$:\n"
            "  $$\\text{EMAT} = h \\times (t_{tlb} + t_{mem}) + (1 - h) \\times (t_{tlb} + 2 \\cdot t_{mem})$$\n"
            "- **Multi-Level Paging:** For a $k$-level page table without TLB, accessing a memory word requires $k + 1$ physical memory accesses."
        ),
    },
    "dijkstra": {
        "keywords": ["dijkstra", "dijkstra's", "single source shortest path", "shortest path algorithm"],
        "title": "Dijkstra's Shortest Path Algorithm",
        "markdown": (
            "### 1. Definition & Core Concept\n"
            "**Dijkstra's Algorithm** is a greedy algorithm that solves the **Single-Source Shortest Path (SSSP)** problem for directed "
            "or undirected graphs with **non-negative edge weights** ($w(u, v) \\ge 0$). It computes the shortest distance from a starting source "
            "vertex $s$ to all other vertices in the graph.\n\n"
            "### 2. How It Works (Greedy Relaxation)\n"
            "1. Maintain a distance array `dist[]` initialized to $\\infty$, setting `dist[source] = 0`.\n"
            "2. Maintain a set of visited vertices $S$. Initially $S = \\emptyset$.\n"
            "3. At each step:\n"
            "   - Extract the unvisited vertex $u \\notin S$ having the minimum `dist[u]` (using a Min-Heap / Priority Queue).\n"
            "   - Add $u$ to $S$.\n"
            "   - **Relax** all outgoing edges $(u, v)$:\n"
            "     $$\\text{if } \\text{dist}[u] + w(u, v) < \\text{dist}[v] \\implies \\text{dist}[v] = \\text{dist}[u] + w(u, v)$$\n"
            "4. Repeat until all reachable vertices are processed.\n\n"
            "### 3. Clear, Intuitive Example\n"
            "Consider vertices $S, A, B$ with edges $S \\to A = 2$, $S \\to B = 5$, and $A \\to B = 1$:\n"
            "- Step 1: Start at $S$: `dist = [S:0, A:2, B:5]`.\n"
            "- Step 2: Extract minimum unvisited vertex $A$ (`dist[A] = 2`).\n"
            "- Step 3: Relax neighbor $B$ from $A$: $\\text{dist}[A] + w(A, B) = 2 + 1 = 3 < 5$. Update `dist[B] = 3`.\n"
            "- Step 4: Extract $B$ (`dist[B] = 3`). Shortest paths finalized: $S \\to A = 2$, $S \\to B = 3$.\n\n"
            "### 4. Key Properties & Time Complexity\n"
            "| Implementation | Time Complexity | Notes |\n"
            "| :--- | :--- | :--- |\n"
            "| Adjacency Matrix + Linear Scan | $O(V^2)$ | Optimal for dense graphs where $E \\approx V^2$ |\n"
            "| Adjacency List + Binary Min-Heap | $O((V + E) \\log V)$ | Standard optimal choice for sparse graphs |\n"
            "| Adjacency List + Fibonacci Heap | $O(E + V \\log V)$ | Theoretically fastest (amortized decrease-key) |\n\n"
            "### 5. GATE Exam Takeaways & Limitations\n"
            "- **CRITICAL LIMITATION:** Dijkstra's algorithm **FAILS on graphs with negative edge weights**, even if there are no negative cycles! (Use **Bellman-Ford**, $O(V \\cdot E)$, when negative edge weights exist).\n"
            "- **Relaxation Count:** Each vertex is extracted and finalized at most once when edge weights are strictly non-negative."
        ),
    },
    "scheduling": {
        "keywords": ["cpu scheduling", "round robin", "fcfs", "sjf", "srtf", "turnaround time", "waiting time", "convoy effect"],
        "title": "CPU Scheduling in Operating Systems",
        "markdown": (
            "### 1. Definition & Core Concept\n"
            "**CPU Scheduling** is the process by which the OS kernel's short-term scheduler selects a process from the Ready Queue "
            "to allocate the CPU, maximizing CPU utilization and throughput while minimizing turnaround, waiting, and response times.\n\n"
            "### 2. Core Scheduling Algorithms\n"
            "1. **FCFS (First-Come, First-Served):** Non-preemptive. Suffers from the **Convoy Effect** (short processes wait behind long ones).\n"
            "2. **SJF (Shortest Job First):** Non-preemptive. Provably optimal minimum average waiting time, but requires knowing burst times in advance.\n"
            "3. **SRTF (Shortest Remaining Time First):** Preemptive version of SJF. Preempts current process if a new process arrives with shorter burst.\n"
            "4. **Round Robin (RR):** Preemptive with a fixed Time Quantum ($q$). Designed for time-sharing systems. Starvation-free.\n\n"
            "### 3. Clear Example & Key Formulae\n"
            "- **Turnaround Time (TAT):** $\\text{Completion Time} - \\text{Arrival Time}$\n"
            "- **Waiting Time (WT):** $\\text{Turnaround Time} - \\text{Burst Time}$\n"
            "- **Response Time:** Time from arrival to first CPU allocation.\n\n"
            "### 4. GATE Exam Takeaways\n"
            "- In Round Robin, if Time Quantum $q \\to \\infty$, RR degenerates to FCFS. If $q$ is extremely small, context-switch overhead dominates.\n"
            "- SJF/SRTF can cause starvation for CPU-intensive long processes."
        ),
    },
    "cache": {
        "keywords": ["cache memory", "cache mapping", "direct mapped", "set associative", "associative cache", "cache line", "tag index offset"],
        "title": "Cache Memory & Mapping Techniques",
        "markdown": (
            "### 1. Definition & Core Concept\n"
            "**Cache Memory** is a small, high-speed static RAM (SRAM) placed between the CPU and Main Memory (DRAM) to bridge the speed disparity "
            "by exploiting Temporal and Spatial Locality of Reference.\n\n"
            "### 2. Cache Mapping Techniques\n"
            "1. **Direct Mapped:** Each memory block maps to exactly one specific cache line: $\\text{Line} = \\text{Block} \\pmod{\\text{Lines}}$.\n"
            "   - Address fields: `[ Tag | Line / Index | Block Offset ]`\n"
            "2. **Fully Associative:** A memory block can be placed in ANY cache line. Eliminates conflict misses, requires expensive associative comparators.\n"
            "   - Address fields: `[ Tag | Block Offset ]`\n"
            "3. **$k$-Way Set Associative:** Cache is divided into sets, each containing $k$ lines. A block maps to a set: $\\text{Set} = \\text{Block} \\pmod{\\text{Sets}}$.\n"
            "   - Address fields: `[ Tag | Set Index | Block Offset ]`\n\n"
            "### 3. Key Formulae & GATE Takeaways\n"
            "- Block Offset bits = $\\log_2(\\text{Block Size in Bytes})$\n"
            "- Set Index bits = $\\log_2(\\text{Number of Sets})$, where $\\text{Number of Sets} = \\frac{\\text{Total Cache Size}}{k \\times \\text{Block Size}}$\n"
            "- Tag bits = $\\text{Physical Address bits} - (\\text{Set Index bits} + \\text{Block Offset bits})$\n"
            "- Direct-mapped caches suffer from high conflict misses; increasing associativity reduces conflict misses with diminishing returns past 8-way."
        ),
    },
    "normalization": {
        "keywords": ["normalization", "bcnf", "3nf", "2nf", "1nf", "lossless join", "dependency preserving", "functional dependency"],
        "title": "Database Normalization (1NF, 2NF, 3NF, BCNF)",
        "markdown": (
            "### 1. Definition & Core Concept\n"
            "**Normalization** is a systematic database design technique based on Functional Dependencies (FDs) to eliminate data redundancy "
            "and prevent insertion, deletion, and update anomalies while guaranteeing Lossless Decomposition.\n\n"
            "### 2. Normal Forms Hierarchy (1NF $\\subset$ 2NF $\\subset$ 3NF $\\subset$ BCNF)\n"
            "1. **1NF:** All attribute values must be atomic (no multi-valued or composite attributes).\n"
            "2. **2NF:** Must be in 1NF, and have **no partial dependency** (no non-prime attribute depends on a proper subset of any candidate key).\n"
            "3. **3NF:** Must be in 2NF, and for every non-trivial FD $X \\to Y$:\n"
            "   - $X$ is a Super Key, OR $Y$ is a Prime Attribute (member of some candidate key).\n"
            "4. **BCNF (Boyce-Codd Normal Form):** Strictly requires that for every non-trivial FD $X \\to Y$, $X$ MUST be a Super Key.\n\n"
            "### 3. GATE Exam Takeaways\n"
            "- **Lossless Join vs. Dependency Preservation:**\n"
            "  * Any relation schema can ALWAYS be decomposed into **3NF** satisfying **both** Lossless Join and Dependency Preservation.\n"
            "  * Decomposing into **BCNF** is ALWAYS Lossless, but Dependency Preservation is **NOT guaranteed**."
        ),
    },
    "bst_avl": {
        "keywords": ["avl tree", "avl trees", "binary search tree", "bst", "balance factor", "avl rotation"],
        "title": "Binary Search Trees & AVL Trees",
        "markdown": (
            "### 1. Definition & Core Concept\n"
            "A **Binary Search Tree (BST)** is a binary tree where for every node $X$, all keys in the left subtree are $< X$ and all keys in the right "
            "subtree are $> X$. Inorder traversal of a BST always yields keys in strictly sorted ascending order.\n\n"
            "An **AVL Tree** is a strictly self-balancing BST where the **Balance Factor** ($BF = \\text{Height}(Left) - \\text{Height}(Right)$) "
            "of every node is strictly in $\\{-1, 0, +1\\}$.\n\n"
            "### 2. AVL Rotations & Rebalancing\n"
            "When an insertion or deletion causes $BF \\notin \\{-1, 0, +1\\}$, one of four rotations restores balance:\n"
            "1. **LL Rotation (Single Right Rotation):** Applied when insertion occurs in left child's left subtree.\n"
            "2. **RR Rotation (Single Left Rotation):** Applied when insertion occurs in right child's right subtree.\n"
            "3. **LR Rotation (Left-Right Double Rotation):** Left rotation on left child, then right rotation on root.\n"
            "4. **RL Rotation (Right-Left Double Rotation):** Right rotation on right child, then left rotation on root.\n\n"
            "### 3. GATE Exam Takeaways\n"
            "- Worst-case search, insertion, and deletion time in AVL trees is strictly $O(\\log n)$.\n"
            "- Minimum nodes in an AVL tree of height $h$: $N(h) = N(h - 1) + N(h - 2) + 1$, where $N(0) = 1, N(1) = 2$."
        ),
    },
}


def lookup_offline_concept(query: str) -> Optional[Dict[str, Any]]:
    """Look up a concept from the curated offline knowledge base."""
    q_lower = query.lower()
    for concept_key, concept_data in OFFLINE_CONCEPT_KNOWLEDGE_BASE.items():
        for kw in concept_data["keywords"]:
            if re.search(r"\b" + re.escape(kw) + r"\b", q_lower):
                return concept_data
    return None


class RagTutorEngine:
    def __init__(self) -> None:
        self.embedder = LazyEmbeddingService.get_instance()

    def retrieve_context(
        self,
        conn: sqlite3.Connection,
        query: str,
        paper_code: Optional[str] = None,
        subject_name: Optional[str] = None,
        topic_name: Optional[str] = None,
        examination_year: Optional[int] = None,
        top_k: int = 5,
        enforce_relevance: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves context from questions table with an active Calibrated Relevance Guard.
        Excludes unrelated noise candidates when enforce_relevance is True.
        """
        sql = """
            SELECT
                q.id, q.paper_code, q.examination_year, q.question_number,
                q.question_type, q.question_text, q.marks, q.negative_marks,
                q.page_number, q.subject_name, q.primary_topic_name, q.subtopic_name,
                q.difficulty_level, q.is_verified, q.is_ai_generated,
                qp.title AS paper_title, qp.filename AS paper_filename,
                ak.correct_options_json, ak.numerical_min, ak.numerical_max,
                ak.provenance AS answer_provenance, ak.explanation AS answer_explanation,
                qe.embedding_vector, qe.embedding_version
            FROM questions q
            LEFT JOIN question_papers qp ON qp.id = q.question_paper_id
            LEFT JOIN answer_keys ak ON ak.question_id = q.id
            LEFT JOIN question_embeddings qe ON qe.question_id = q.id
            WHERE 1=1
        """
        params: List[Any] = []
        if paper_code:
            sql += " AND q.paper_code = ?"
            params.append(paper_code.upper())
        if subject_name:
            sql += " AND q.subject_name = ?"
            params.append(subject_name)
        if topic_name:
            sql += " AND q.primary_topic_name = ?"
            params.append(topic_name)
        if examination_year:
            sql += " AND q.examination_year = ?"
            params.append(int(examination_year))

        rows = conn.execute(sql, params).fetchall()
        if not rows:
            return []

        q_vec, _, q_ver = self.embedder.embed_text(query)
        scored: List[Dict[str, Any]] = []

        for r in rows:
            q_text, _ = sanitize_untrusted_pdf_text(r["question_text"] or "")
            target_str = f"{q_text} {r['subject_name'] or ''} {r['primary_topic_name'] or ''}"
            tfidf_sim = self.embedder.tfidf_cosine(query, target_str)
            emb_sim = 0.0
            if r["embedding_vector"] and r["embedding_version"] == q_ver:
                try:
                    stored_vec = json.loads(r["embedding_vector"])
                    emb_sim = self.embedder.cosine_similarity(q_vec, stored_vec)
                except Exception:
                    emb_sim = 0.0
            else:
                cand_vec, _, _ = self.embedder.embed_text(q_text)
                emb_sim = self.embedder.cosine_similarity(q_vec, cand_vec)

            combined_score = 0.55 * emb_sim + 0.45 * tfidf_sim

            # Filter out candidates that fail the relevance guard
            if enforce_relevance and not is_retrieval_relevant(combined_score, tfidf_sim, emb_sim):
                continue

            # Fetch options for this question
            opt_rows = conn.execute(
                "SELECT option_label, option_text, is_correct FROM question_options WHERE question_id = ? ORDER BY option_label",
                (r["id"],),
            ).fetchall()
            options = [
                {
                    "option_label": o["option_label"],
                    "option_text": o["option_text"],
                    "is_correct": bool(o["is_correct"]) if o["is_correct"] is not None else None,
                }
                for o in opt_rows
            ]

            correct_opts = []
            if r["correct_options_json"]:
                try:
                    correct_opts = json.loads(r["correct_options_json"])
                except Exception:
                    correct_opts = []

            scored.append(
                {
                    "question_id": r["id"],
                    "paper_code": r["paper_code"],
                    "examination_year": r["examination_year"],
                    "question_number": r["question_number"],
                    "question_type": r["question_type"],
                    "question_text": q_text,
                    "marks": r["marks"],
                    "negative_marks": r["negative_marks"],
                    "page_number": r["page_number"],
                    "subject_name": r["subject_name"],
                    "topic_name": r["primary_topic_name"],
                    "subtopic_name": r["subtopic_name"],
                    "difficulty_level": r["difficulty_level"],
                    "paper_title": r["paper_title"] or f"GATE {r['paper_code']} {r['examination_year']}",
                    "paper_filename": r["paper_filename"],
                    "options": options,
                    "answer_provenance": r["answer_provenance"] or "unverified",
                    "correct_options": correct_opts,
                    "numerical_range": (
                        [r["numerical_min"], r["numerical_max"]]
                        if r["numerical_min"] is not None
                        else None
                    ),
                    "verified_explanation": r["answer_explanation"],
                    "similarity_score": round(float(combined_score), 4),
                    "citation": f"GATE {r['paper_code']} {r['examination_year']}, Q.{r['question_number']} (Page {r['page_number']})",
                }
            )

        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        return scored[:top_k]

    def lookup_exact_question(
        self,
        conn: sqlite3.Connection,
        question_number: int,
        paper_code: Optional[str] = None,
        year: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Look up an exact question by number, year, and paper code."""
        sql = """
            SELECT
                q.id, q.paper_code, q.examination_year, q.question_number,
                q.question_type, q.question_text, q.marks, q.negative_marks,
                q.page_number, q.subject_name, q.primary_topic_name, q.subtopic_name,
                q.difficulty_level, q.is_verified, q.is_ai_generated,
                qp.title AS paper_title, qp.filename AS paper_filename,
                ak.correct_options_json, ak.numerical_min, ak.numerical_max,
                ak.provenance AS answer_provenance, ak.explanation AS answer_explanation
            FROM questions q
            LEFT JOIN question_papers qp ON qp.id = q.question_paper_id
            LEFT JOIN answer_keys ak ON ak.question_id = q.id
            WHERE q.question_number = ?
        """
        params: List[Any] = [question_number]
        if paper_code:
            sql += " AND q.paper_code = ?"
            params.append(paper_code.upper())
        if year:
            sql += " AND q.examination_year = ?"
            params.append(int(year))
        sql += " ORDER BY q.examination_year DESC LIMIT 1"

        row = conn.execute(sql, params).fetchone()
        if not row:
            return None

        opt_rows = conn.execute(
            "SELECT option_label, option_text, is_correct FROM question_options WHERE question_id = ? ORDER BY option_label",
            (row["id"],),
        ).fetchall()
        options = [
            {
                "option_label": o["option_label"],
                "option_text": o["option_text"],
                "is_correct": bool(o["is_correct"]) if o["is_correct"] is not None else None,
            }
            for o in opt_rows
        ]

        correct_opts = []
        if row["correct_options_json"]:
            try:
                correct_opts = json.loads(row["correct_options_json"])
            except Exception:
                correct_opts = []

        q_text, _ = sanitize_untrusted_pdf_text(row["question_text"] or "")
        return {
            "question_id": row["id"],
            "paper_code": row["paper_code"],
            "examination_year": row["examination_year"],
            "question_number": row["question_number"],
            "question_type": row["question_type"],
            "question_text": q_text,
            "marks": row["marks"],
            "negative_marks": row["negative_marks"],
            "page_number": row["page_number"],
            "subject_name": row["subject_name"],
            "topic_name": row["primary_topic_name"],
            "subtopic_name": row["subtopic_name"],
            "difficulty_level": row["difficulty_level"],
            "paper_title": row["paper_title"] or f"GATE {row['paper_code']} {row['examination_year']}",
            "paper_filename": row["paper_filename"],
            "options": options,
            "answer_provenance": row["answer_provenance"] or "unverified",
            "correct_options": correct_opts,
            "numerical_range": (
                [row["numerical_min"], row["numerical_max"]]
                if row["numerical_min"] is not None
                else None
            ),
            "verified_explanation": row["answer_explanation"],
            "citation": f"GATE {row['paper_code']} {row['examination_year']}, Q.{row['question_number']} (Page {row['page_number']})",
        }

    def answer_student_query(
        self,
        conn: sqlite3.Connection,
        query: str,
        paper_code: Optional[str] = "CS",
        subject_name: Optional[str] = None,
        topic_name: Optional[str] = None,
        examination_year: Optional[int] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Intent-routed AI Tutor handler. Routes dynamically to:
        - _handle_conceptual_query
        - _handle_specific_question
        - _handle_pyq_search
        - _handle_hybrid_query
        """
        parsed = classify_tutor_intent(query)
        intent = parsed["intent"]

        if intent == "specific_question":
            return self._handle_specific_question(
                conn=conn,
                query=query,
                parsed=parsed,
                default_paper_code=paper_code,
                default_year=examination_year,
            )

        if intent == "conceptual":
            return self._handle_conceptual_query(
                query=query,
                parsed=parsed,
                paper_code=paper_code,
            )

        if intent == "hybrid":
            return self._handle_hybrid_query(
                conn=conn,
                query=query,
                parsed=parsed,
                paper_code=paper_code,
                subject_name=subject_name,
                topic_name=topic_name,
                examination_year=examination_year,
                top_k=top_k,
            )

        # Default intent: pyq_search
        return self._handle_pyq_search(
            conn=conn,
            query=query,
            parsed=parsed,
            paper_code=paper_code,
            subject_name=subject_name,
            topic_name=topic_name,
            examination_year=examination_year,
            top_k=top_k,
        )

    def _handle_conceptual_query(
        self,
        query: str,
        parsed: Dict[str, Any],
        paper_code: Optional[str] = "CS",
    ) -> Dict[str, Any]:
        """Handles conceptual queries without retrieving PYQs."""
        # 1. Try Gemini API if configured
        if settings.GEMINI_API_KEY:
            try:
                from google import genai

                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                prompt = (
                    "You are Agent 6 (AI Tutor) in GATE Intelligence.\n"
                    "The student has asked a conceptual question. Provide a direct, comprehensive, educational explanation.\n\n"
                    "Use the following structured teaching format:\n"
                    "### 1. Definition & Core Concept\n"
                    "### 2. How It Works (Mechanism & Architecture)\n"
                    "### 3. Clear, Intuitive Example\n"
                    "### 4. Key Properties, Constraints & Formulae\n"
                    "### 5. GATE Exam Takeaways (Common Pitfalls & Tricks)\n\n"
                    "Do NOT fabricate any fake GATE question numbers, options, or official answer keys. "
                    "Focus purely on teaching the concept.\n\n"
                    f"Student Query: {query}"
                )
                resp = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                )
                if resp and getattr(resp, "text", None):
                    return {
                        "query": query,
                        "answer_markdown": resp.text,
                        "answer_provenance": "conceptual_explanation",
                        "provenance_badge": "Conceptual Guide (AI Synthesis)",
                        "citations": [],
                        "related_questions": [],
                        "model_used": settings.GEMINI_MODEL,
                    }
            except Exception:
                pass

        # 2. Local / Offline mode: check curated concept knowledge base
        concept = lookup_offline_concept(query)
        if concept:
            return {
                "query": query,
                "answer_markdown": f"## {concept['title']}\n\n{concept['markdown']}",
                "answer_provenance": "conceptual_explanation",
                "provenance_badge": "Conceptual Guide (Offline Knowledge Base)",
                "citations": [],
                "related_questions": [],
                "model_used": "offline-concept-knowledge-base",
            }

        # 3. Transparent fallback if topic is not in offline knowledge base
        clean_topic = parsed.get("cleaned_query") or query
        clean_topic = re.sub(r"^(?:explain|what\s+is|what\s+are|define|describe)\s+", "", clean_topic, flags=re.IGNORECASE).strip(".? ")
        return {
            "query": query,
            "answer_markdown": (
                f"### Conceptual Explanation: `{clean_topic.title()}`\n\n"
                "**Offline Mode Notice:** No `GEMINI_API_KEY` is configured in your environment, and this specific topic "
                "is not included in the local offline concept knowledge base.\n\n"
                "**Available Capabilities:**\n"
                "1. **Core GATE Concepts Available Offline:** You can ask for complete structured guides on:\n"
                "   - *Operating Systems:* Deadlock, Semaphores, Paging & Virtual Memory, CPU Scheduling\n"
                "   - *Algorithms & Data Structures:* Dijkstra's Algorithm, BST & AVL Trees\n"
                "   - *Computer Architecture & DBMS:* Cache Memory & Mapping, Database Normalization (3NF/BCNF)\n"
                "2. **Enable AI Synthesis:** Add your `GEMINI_API_KEY` in `.env` to generate comprehensive conceptual tutorials for any topic across all 30 GATE disciplines.\n"
                "3. **Search Question Bank:** Search for authentic questions using `Find GATE questions on ...`"
            ),
            "answer_provenance": "unverified",
            "provenance_badge": "Offline Mode (Key Required for Custom Topics)",
            "citations": [],
            "related_questions": [],
            "model_used": "offline-tutor-limitation",
        }

    def _handle_specific_question(
        self,
        conn: sqlite3.Connection,
        query: str,
        parsed: Dict[str, Any],
        default_paper_code: Optional[str] = "CS",
        default_year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Handles exact question lookup (e.g. 'Solve GATE CS 2012 Question 32')."""
        q_num = parsed.get("question_number")
        year = parsed.get("year") or default_year
        p_code = parsed.get("paper_code") or default_paper_code or "CS"

        if not q_num:
            return self._handle_pyq_search(conn, query, parsed, p_code, None, None, year)

        q_record = self.lookup_exact_question(conn, question_number=q_num, paper_code=p_code, year=year)
        if not q_record:
            year_str = f" {year}" if year else ""
            return {
                "query": query,
                "answer_markdown": (
                    f"### GATE {p_code}{year_str} Question {q_num} Not Found\n\n"
                    f"Question **Q.{q_num}** for GATE {p_code}{year_str} was not found in the current question bank.\n\n"
                    "**Troubleshooting:**\n"
                    f"- Verify that the question paper for GATE {p_code}{year_str} has been uploaded and processed in the **Paper Library**.\n"
                    "- Verify the question number in the **Question Bank**.\n"
                    "- GATE CS question papers typically contain questions numbered 1 to 65."
                ),
                "answer_provenance": "unverified",
                "provenance_badge": "Question Not Found",
                "citations": [],
                "related_questions": [],
                "model_used": "exact-question-lookup",
            }

        # Try Gemini if configured
        if settings.GEMINI_API_KEY:
            try:
                from google import genai

                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                q_context = json.dumps(q_record, indent=2)
                prompt = (
                    "You are Agent 6 (AI Tutor) in GATE Intelligence.\n"
                    "The student has asked to solve a specific previous-year question.\n"
                    "Provide a step-by-step mathematical and conceptual solution.\n"
                    "Show the question statement, analyze each option, derive the answer, and highlight key GATE exam tricks.\n\n"
                    f"GATE Question Record:\n{q_context}\n\n"
                    f"Student Query: {query}"
                )
                resp = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                )
                if resp and getattr(resp, "text", None):
                    return {
                        "query": query,
                        "answer_markdown": resp.text,
                        "answer_provenance": q_record["answer_provenance"],
                        "provenance_badge": self._format_provenance_badge([q_record]),
                        "citations": [q_record["citation"]],
                        "related_questions": [q_record],
                        "model_used": settings.GEMINI_MODEL,
                    }
            except Exception:
                pass

        # Offline / deterministic solution for the exact question
        lines = [
            f"### Solution for `{q_record['citation']}`",
            f"**Discipline & Topic:** *{q_record['subject_name']} → {q_record['topic_name']}* ({q_record['question_type']}, {q_record['marks']} Mark(s))",
            f"**Answer Provenance:** `{q_record['answer_provenance']}` ({self._format_provenance_badge([q_record])})",
            "",
            "#### Question Statement",
            f"> {q_record['question_text']}",
            "",
        ]
        if q_record["options"]:
            lines.append("#### Options")
            for opt in q_record["options"]:
                lbl = opt["option_label"]
                is_c = lbl in (q_record["correct_options"] or [])
                status_icon = "✅" if is_c else "⚪"
                lines.append(f"- **({lbl})** {opt['option_text']} {status_icon if q_record['answer_provenance'] in ('official_key', 'manually_verified') else ''}")
            lines.append("")

        lines.append("#### Step-by-Step Derivation & Explanation")
        if q_record.get("verified_explanation"):
            lines.append(q_record["verified_explanation"])
        else:
            lines.append(
                f"1. **Core Concept:** This question evaluates knowledge of **{q_record['topic_name']}** under **{q_record['subject_name']}**.\n"
                f"2. **Marking Scheme:** As a **{q_record['question_type']}** question carrying **{q_record['marks']} mark(s)**, "
                f"an incorrect response receives a **-{round(q_record['negative_marks'], 2)}** penalty.\n"
                f"3. **Provenance Notice:** Official answer key provenance is `{q_record['answer_provenance']}`."
            )

        return {
            "query": query,
            "answer_markdown": "\n".join(lines),
            "answer_provenance": q_record["answer_provenance"],
            "provenance_badge": self._format_provenance_badge([q_record]),
            "citations": [q_record["citation"]],
            "related_questions": [q_record],
            "model_used": "exact-question-solver",
        }

    def _handle_pyq_search(
        self,
        conn: sqlite3.Connection,
        query: str,
        parsed: Dict[str, Any],
        paper_code: Optional[str] = "CS",
        subject_name: Optional[str] = None,
        topic_name: Optional[str] = None,
        examination_year: Optional[int] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Handles searching for relevant PYQs using the relevance guard."""
        clean_q = parsed.get("cleaned_query") or query
        # Strip search commands
        clean_q = re.sub(r"^(?:find|search|show|get|list|give\s+me)\s+(?:all\s+)?(?:previous\s*year|past\s*year|gate\s+)?(?:questions?|pyqs?|problems?)\s+(?:on|about|for|related\s+to)?\s*", "", clean_q, flags=re.IGNORECASE).strip(".? ")
        if not clean_q:
            clean_q = query

        retrieved = self.retrieve_context(
            conn=conn,
            query=clean_q,
            paper_code=paper_code,
            subject_name=subject_name,
            topic_name=topic_name,
            examination_year=examination_year,
            top_k=top_k,
            enforce_relevance=True,
        )

        if not retrieved:
            return {
                "query": query,
                "answer_markdown": (
                    f"### Previous-Year Questions Search: `{clean_q}`\n\n"
                    f"**No matching previous-year questions found in the uploaded repository.**\n\n"
                    f"No questions with sufficient relevance to **'{clean_q}'** were found in the currently loaded examination papers (GATE {paper_code or 'All'}).\n\n"
                    "**Suggestions:**\n"
                    "- Upload additional GATE paper PDFs in the **Paper Library**.\n"
                    "- Broaden your search query (e.g. search by broader subject name).\n"
                    f"- Ask for a conceptual explanation using `Explain {clean_q}`."
                ),
                "answer_provenance": "unverified",
                "provenance_badge": "No Uploaded PYQs Found",
                "citations": [],
                "related_questions": [],
                "model_used": "rag-tutor-search",
            }

        # Try Gemini if configured
        if settings.GEMINI_API_KEY:
            try:
                from google import genai

                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                context_block = json.dumps(retrieved, indent=2)
                prompt = (
                    "You are Agent 6 (RAG-Based AI Tutor) in GATE Intelligence.\n"
                    "The student is searching for previous-year questions related to their query.\n"
                    "Present the retrieved questions clearly, explain their core concepts, and provide analytical solutions.\n"
                    "Explicitly cite each question's examination year, question number, and page.\n\n"
                    f"Retrieved GATE Questions:\n{context_block}\n\n"
                    f"Student Search Query: {query}"
                )
                resp = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                )
                if resp and getattr(resp, "text", None):
                    return {
                        "query": query,
                        "answer_markdown": resp.text,
                        "answer_provenance": (
                            retrieved[0]["answer_provenance"]
                            if retrieved and retrieved[0]["answer_provenance"] in ("official_key", "manually_verified")
                            else "ai_generated"
                        ),
                        "provenance_badge": self._format_provenance_badge(retrieved),
                        "citations": [r["citation"] for r in retrieved],
                        "related_questions": retrieved,
                        "model_used": settings.GEMINI_MODEL,
                    }
            except Exception:
                pass

        # Offline / deterministic synthesis of retrieved questions
        lines = [
            f"### GATE Previous-Year Questions Matching `{clean_q}`",
            f"Found **{len(retrieved)}** relevant question(s) in the uploaded question bank.",
            "",
        ]
        for idx, q in enumerate(retrieved, 1):
            lines.extend([
                f"#### {idx}. {q['citation']} — *{q['subject_name']} → {q['topic_name']}*",
                f"**Type:** {q['question_type']} | **Marks:** {q['marks']} (Neg: -{round(q['negative_marks'], 2)}) | **Provenance:** `{q['answer_provenance']}`",
                f"> {q['question_text']}",
                "",
            ])
            if q["options"]:
                lines.append("**Options:**")
                for opt in q["options"]:
                    is_c = opt["option_label"] in (q["correct_options"] or [])
                    icon = "✅ (Official Key)" if is_c and q["answer_provenance"] == "official_key" else ""
                    lines.append(f"- **({opt['option_label']})** {opt['option_text']} {icon}")
                lines.append("")

            if q.get("verified_explanation"):
                lines.append(f"**Explanation:** {q['verified_explanation']}\n")

        return {
            "query": query,
            "answer_markdown": "\n".join(lines),
            "answer_provenance": (
                retrieved[0]["answer_provenance"]
                if retrieved and retrieved[0]["answer_provenance"] in ("official_key", "manually_verified")
                else "ai_generated"
            ),
            "provenance_badge": self._format_provenance_badge(retrieved),
            "citations": [r["citation"] for r in retrieved],
            "related_questions": retrieved,
            "model_used": "rag-tutor-search",
        }

    def _handle_hybrid_query(
        self,
        conn: sqlite3.Connection,
        query: str,
        parsed: Dict[str, Any],
        paper_code: Optional[str] = "CS",
        subject_name: Optional[str] = None,
        topic_name: Optional[str] = None,
        examination_year: Optional[int] = None,
        top_k: int = 3,
    ) -> Dict[str, Any]:
        """Handles hybrid queries: conceptual explanation first, then relevant PYQs."""
        # 1. Generate conceptual explanation
        concept_res = self._handle_conceptual_query(query, parsed, paper_code)
        concept_markdown = concept_res["answer_markdown"]

        # 2. Extract search term and search for relevant PYQs with relevance guard
        clean_q = parsed.get("cleaned_query") or query
        clean_q = re.sub(r"\b(?:and\s+then\s+(?:find|show|give|retrieve|solve|look\s*up)|along\s+with|with\s+related)\s+(?:gate\s+)?(?:pyqs?|questions?)\b", "", clean_q, flags=re.IGNORECASE)
        clean_q = re.sub(r"^(?:explain|what\s+is|what\s+are|define|describe)\s+", "", clean_q, flags=re.IGNORECASE).strip(".? ")

        retrieved = self.retrieve_context(
            conn=conn,
            query=clean_q or query,
            paper_code=paper_code,
            subject_name=subject_name,
            topic_name=topic_name,
            examination_year=examination_year,
            top_k=top_k,
            enforce_relevance=True,
        )

        # 3. Assemble combined response
        combined_lines = [
            concept_markdown,
            "",
            "---",
            "### Related GATE Previous-Year Questions",
        ]
        if retrieved:
            combined_lines.append(f"Found **{len(retrieved)}** relevant previous-year question(s) for this topic:\n")
            for idx, q in enumerate(retrieved, 1):
                combined_lines.extend([
                    f"#### {idx}. {q['citation']} — *{q['subject_name']} → {q['topic_name']}*",
                    f"**Type:** {q['question_type']} | **Marks:** {q['marks']} | **Provenance:** `{q['answer_provenance']}`",
                    f"> {q['question_text']}",
                    "",
                ])
                if q["options"]:
                    for opt in q["options"]:
                        is_c = opt["option_label"] in (q["correct_options"] or [])
                        icon = "✅" if is_c and q["answer_provenance"] in ("official_key", "manually_verified") else ""
                        combined_lines.append(f"- **({opt['option_label']})** {opt['option_text']} {icon}")
                    combined_lines.append("")
        else:
            combined_lines.append(
                f"*No matching previous-year questions found in the currently loaded papers for '{clean_q}'.*"
            )

        return {
            "query": query,
            "answer_markdown": "\n".join(combined_lines),
            "answer_provenance": "conceptual_explanation",
            "provenance_badge": "Conceptual Guide + PYQ Search",
            "citations": [r["citation"] for r in retrieved],
            "related_questions": retrieved,
            "model_used": concept_res.get("model_used", "hybrid-tutor-engine"),
        }

    @staticmethod
    def _format_provenance_badge(retrieved: List[Dict[str, Any]]) -> str:
        if not retrieved:
            return "Unverified"
        prov = retrieved[0].get("answer_provenance", "unverified")
        return {
            "official_key": "Official Answer Key",
            "manually_verified": "Manually Verified",
            "ai_generated": "AI-Generated Solution",
            "unverified": "Unverified Source",
            "conceptual_explanation": "Conceptual Guide (AI Synthesis)",
        }.get(prov, "Unverified Source")
