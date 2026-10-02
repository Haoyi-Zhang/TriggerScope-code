# Mathematical specification and complete arguments

These are ordinary mathematical proofs. Executable finite tests support the implementation but are not a proof-assistant formalization. Hall's theorem, finite-state dynamic programming, and the certifying-algorithm paradigm are classical ingredients; no priority claim is made for them.

## 1. Trace classes and the report contract

Let U be a nonempty finite set of legal traces, equipped with shortlex order from a declared finite ordered event alphabet. A fixed total semantic map s:U -> {0,1}^r assigns the final trigger-output vector. Its nonempty fibers C_0,...,C_{k-1} partition U. Order them by their least shortlex representatives rho_c. A disjoint observation partition h:U -> Y gives cells U_yc = h^{-1}(y) intersect C_c with exact nonnegative integer capacities N_yc. Every class has positive total capacity. Empty observation buckets can be omitted.

A report n specifies n_y distinct selected traces in each bucket. Its compatible reports are exactly all subsets R of U satisfying |R intersect h^{-1}(y)|=n_y. Assume 0<=n_y<=N_y where N_y=sum_c N_yc. There are no additional cross-trace constraints, and multiplicities of repeated executions are not counted. Under these assumptions this family is nonempty: select any n_y distinct elements from each disjoint bucket and take the union.

For any compatible R, let o(R) be the first class absent from R, or k if all classes occur. The omission spectrum is Omega(N,n)={o(R): R compatible}. Sentinel k denotes COMPLETE, not an additional semantic class.

### Lemma 1: Allocation realizability

The compatible reports have exactly the same outcome set as integer matrices X satisfying 0<=X_yc<=N_yc and sum_c X_yc=n_y. For a report, take X_yc=|R intersect U_yc|. Conversely choose X_yc distinct tokens in each cell. Cells are disjoint, so all choices can be made simultaneously; their union is a compatible report. Nonemptiness of column c in X is equivalent to class representation. This argument would fail for extra constraints coupling selected traces.

### Lemma 2: Class exclusion and forcing

Class c is absent in some compatible report iff n_y<=N_y-N_yc for every y. Necessity follows from the capacity outside c in each bucket. Sufficiency follows by independently selecting n_y outside-c tokens in every bucket. Consequently, c is present in every compatible report iff at least one bucket satisfies n_y>N_y-N_yc.

Class c can be present in some compatible report iff N_yc>0 and n_y>0 for some bucket y. Put one c token there and fill the remaining row counts. This marginal condition alone does not imply that all classes can be present together.

## 2. Simultaneous coverage and the filling lemma

Construct a bipartite support graph with a vertex for each class, a vertex for each bucket, and edge c--y iff N_yc>0. A matching here assigns each required class to one incident bucket; bucket y receives at most n_y classes. Classes have unit demand, buckets have integer capacity n_y. This can also be regarded as ordinary matching after duplicating a bucket n_y times, but the implementation does not materialize those copies.

### Lemma 3: Matching plus exclusion is sufficient

Let P be required classes and E be excluded classes, with P intersect E empty. There is a compatible report representing every class in P and no class in E iff (i) the support graph admits a capacitated matching of P and (ii) for each y, n_y<=sum_{c not in E} N_yc.

Necessity: choose one selected trace from each required class. The chosen traces are distinct because classes are disjoint. Assign a required class to that trace's bucket. The number assigned to y is no larger than the report's n_y; every edge has positive capacity. Exclusion gives (ii).

Sufficiency: reserve one trace in U_yc for each matched pair (c,y). A class is matched only once, so no cell is asked to reserve more than one token; every such cell has positive capacity. Write a_y for the number reserved in bucket y. All reserved tokens lie outside E and a_y<=n_y. The total remaining capacity outside E is sum_{c not in E}N_yc-a_y >= n_y-a_y. Choose that many additional distinct tokens from the remaining cells, independently for each bucket. The resulting report meets all row counts, includes P, and excludes E.

This is the crucial extension step. A matching alone does not prove that an excluded class can be avoided while filling all report counts. Conversely, class-by-class exclusion tests alone do not prove that earlier classes can all fit in the selected slots.

For E empty, condition (ii) is the report-validity assumption. Thus P is simultaneously coverable exactly when its support graph has a capacitated matching. The capacitated Hall criterion is |T|<=sum_{y in Gamma(T)} n_y for all T subset P. It follows from ordinary Hall's theorem by conceptual bucket cloning, or directly from integral flow.

## 3. Prefix bottleneck and the exact spectrum

Let P_j={0,...,j-1}. Let p be the maximum j in {0,...,k} such that P_j is simultaneously coverable. Prefix feasibility is monotone, since a matching for a larger prefix restricts to a smaller prefix.

### Theorem 1: Exact canonical-omission spectrum

Let A={c<k: for all y, n_y<=N_y-N_yc}. Then

Omega(N,n) = (A intersect {0,...,p}) union ({k} if p=k, otherwise empty).

For c<k, if a report's first omitted class is c, it covers P_c and avoids c. Hence c<=p and c belongs to A. Conversely if c<=p and c belongs to A, restrict a matching of P_p to P_c and apply Lemma 3 with P=P_c and E={c}. The constructed report represents every earlier class and excludes c, so its first omitted class is exactly c. For COMPLETE, Lemma 3 with P all classes and E empty shows that a complete report exists iff p=k. This proves both inclusions and the sentinel condition.

### Corollary 1: Exact three-way entailment

A valid count report forces complete coverage iff Omega={k}. It forces incomplete coverage iff k is not in Omega. Otherwise it is ambiguous. A unique actual first omitted class is inferable from the count contract iff Omega is a singleton {c} with c<k. The spectrum is never empty because the compatible report family is nonempty.

Forced-complete can equivalently be checked by requiring every class to have a forcing bucket from Lemma 2. Indeed the conjunction of finitely many universal class-coverage properties is universal full coverage. This shortcut does not characterize all possible omissions when coverage is not forced.

### Theorem 2: Prefix certificate

A matching saturating P_p, plus (when p<k) a nonempty T subset P_{p+1} with |T|>sum_{y in Gamma(T)}n_y, proves that p is the longest feasible prefix. The matching proves feasibility through p. If the next prefix had a matching, all members of T would be assigned to Gamma(T), contradicting the capacity inequality. All larger prefixes contain the infeasible next prefix. When p=k, saturation alone suffices.

A producer obtains such a certificate by augmenting a matching in class order until the first failure. After failure at c=p, form alternating reachability starting from p: from reached classes follow every support edge to buckets; from reached buckets follow all their assigned classes. Every reached bucket is full, or an augmenting path to spare capacity would exist. Every reached matched class is assigned inside this reached bucket set, and the only unmatched reached class is p. No assigned class can appear twice. Therefore |T|=1+sum_{y in Gamma(T)}n_y. This supplies the required Hall-deficient set. At successful termination p=k no obstruction is needed.

The matching routine is a standard augmenting-path construction; the checker neither searches for an augmenting path nor trusts the producer's failure report.

## 4. What cannot be inferred

### Theorem 3: No universal binary-or-single-witness answer from counts

Take N=[[1,1],[1,1]] and n=[1,1]. Let each row contain one token of each class. Selecting both class-0 tokens gives outcome 1; selecting both class-1 tokens gives outcome 0; selecting one of each class gives COMPLETE=2. These are indistinguishable count reports, so a deterministic function of (N,n) that claims either actual full coverage or a unique actual omitted class must be wrong for at least one compatible report. Randomization cannot make a universally correct answer possible when the evidence remains identical. An omission spectrum or conditional witnesses can be sound.

This is an information-contract impossibility, not an assertion that arbitrary Android analysis is mathematically beyond investigation.

### A forced-incomplete report with no fixed absent class

Take N=[[1,1,1,0],[0,0,0,3]], n=[2,2]. The first three classes share only two selected slots; the last class has its own bucket. Thus all reports are incomplete although each class is possible in at least one compatible report. The spectrum is {0,1,2}. The first bucket has three equally sized possible selections of two distinct classes, while the second has three choices of two class-3 tokens; there are nine compatible concrete reports. Neither the cardinality threshold sum n=k nor the marginal-possibility condition detects this Hall bottleneck.

### Proposition 1: Refinement monotonicity

Let two evidence contracts describe nonempty compatible families F' subset F over the same ordered semantic classes. Then {o(R):R in F'} subset {o(R):R in F}. Thus verified additional information cannot enlarge the omission spectrum. This is set inclusion, not a claim that adding arbitrary unverified log fields establishes correctness. If the new evidence changes U or the class order, the proposition does not apply without a class-preserving correspondence.

Revealing the full class allocation X collapses the compatible outcomes to one even when exact traces remain undisclosed. Revealing only bucket support or counts need not. This distinguishes evidence needed for a particular instance from a universal requirement to enumerate every trace or class in every certificate.

### Proposition 2: Output-information scope

For fixed k, every subset A of {0,...,k-2} can be realized as the non-COMPLETE portion of a spectrum that also contains COMPLETE. Use k buckets of report count one. Bucket c<k-1 has one c token and, iff c in A, one filler-class (k-1) token. The last bucket contains one filler token. Every class can be matched to its own bucket, so p=k; precisely A is avoidable. Hence there are 2^(k-1) spectra. A self-contained encoding that distinguishes all such sets without access to N needs at least k-1 bits in the worst case (by counting codewords).

This is not an Omega(k) lower bound on every certificate when the input matrix is already supplied, not a lower bound on all instance-specific output sizes, and not a proof that unrestricted explicit enumeration is unavoidable. Uniformly forced-complete reports have a singleton spectrum.

## 5. Source semantics and replay

Each event is a fixed typed record. Guards test equality of kind, value, or context. ever(g) holds iff g is true at some position. last(g) holds iff the trace is nonempty and g is true at its last position. count_t(g) holds iff at least t positions satisfy g; the implementation saturates the counter at t. before(g,h) holds iff there are positions i<j with g at i and h at j. Boolean formulas combine monitor outputs. Empty traces make all primitive monitors false. A before transition must use the old state, so the first event satisfying both guards does not accept.

A state records monitor memories, the final event bucket, and optional locked context. The latter is initially unset, set by the first event, and rejects subsequent differing contexts. Context locking is per trace, not a requirement that all traces selected in a report share one physical context.

### Lemma 4: Layered recurrence

Let Q_d be exactly the states reached by legal words of length d. For q in Q_d, let W_d(q) be the count of such words and L_d(q) their lexicographic minimum. The unique initial state has count 1 and word epsilon. For every q' at layer d+1:

W_{d+1}(q') = sum over legal (q,a) with delta(q,a)=q' of W_d(q).
L_{d+1}(q') = lexmin over the same pairs of (L_d(q) concatenated with a).

Every legal word has one final event and one predecessor word, so the counting families are disjoint and exhaustive. For a fixed predecessor and last event, appending that event preserves lexicographic order on equal-length words; thus its minimum extension is obtained from L_d(q). Taking the minimum across predecessor/event pairs proves the second recurrence. Induction from the initial layer proves both for every d<=H.

### Lemma 5: Source-derived class capacities and order

The joint state determines every final trigger bit and the report bucket at a fixed depth. Summing W_d(q) over admissible depths and states with the same signature and observation yields exactly N_yc. Different lengths and deterministic states partition U, so no trace is counted twice. Taking the shortest then lexicographically smallest L_d(q) across each signature's nodes yields its least representative. Distinct signatures have disjoint trace fibers, so their representatives are distinct. Sorting these representatives establishes the declared canonical class order.

### Theorem 4: Replay soundness and relative completeness

The replay specification validates the initial record, distinct state keys per layer, bounds, every legal outgoing transition's presence in the supplied next layer, the count/minimum-word recurrences, and positive incoming counts for every supplied node. By induction, closure prevents missing reachable states, while positive justified counts prevent spurious states. Lemmas 4 and 5 therefore establish the exact semantic matrix and canonical order independently of the producer's search. The checked matching/cut proves p by Theorem 2, and the exclusion scan gives exactly Omega by Theorem 1. Each optional allocation witness is checked against row counts, capacities, and its first omitted class; Lemma 1 establishes that it denotes a compatible concrete report.

Conversely, for any well-formed admitted source model and valid count report within the declared representation bounds, the producer's complete finite DAG, exact recurrences and canonical representatives pass these semantic checks. Ordered augmentation supplies a valid prefix certificate, and Lemma 3 supplies allocation witnesses for the minimum and maximum outcomes. Thus a valid certificate exists. This is relative completeness for the declared finite model, not for Android code extraction, arbitrary source languages or a faulty checker implementation. The executable checker is tested separately; its general correctness is not machine-verified.

## 6. Boundaries that change the theorem

If repeated runs are counted rather than distinct traces, the capacities N_yc no longer bound selected multiplicities, and the forcing inequalities can be unsound. If only a lower bound on counts is known, the compatible family is not the exact-row-sum family above. If capacity rows overlap, summing counts double-counts shared tokens. If an abstraction has spurious traces, an exact certificate for that abstraction need not certify concrete feasibility. If an abstraction omits concrete traces, the report may force coverage of an incomplete declared universe. Neither direction of approximation can silently replace equality of the source-derived cells.

For cross-trace constraints, label the two tokens in each row of [[1,1],[1,1]] by a common context: both class-0 tokens have context 0, both class-1 tokens have context 1. If a report is additionally required to select a single shared context across all its traces, [1,1] cannot have a complete compatible realization, whereas the unrestricted count theorem permits one. This is a counterexample to dropping the independence assumption, not a checker bug under the stated contract.

The canonical representative of a missing class is the least trace in that whole absent fiber. It is not necessarily the first unexecuted individual trace overall: a represented class may contain unexecuted traces smaller than that representative. No behavioral future-equivalence or bisimulation-minimality claim is needed or established.

## 7. Marginal selected-count interval

For one class c, each row's selected count z lies in the integer interval [max(0,n_y-(N_y-N_yc)), min(n_y,N_yc)]. Every value in that interval is realized by choosing z distinct tokens of the class and n_y-z outside it. Row independence makes the possible sum exactly the integer interval obtained by summing these endpoints. The sum-of-intervals claim follows by induction: for intervals [a,b] and [c,d], every integer t between a+c and b+d admits an integer x in [a,b] intersect [t-d,t-c], and t-x lies in [c,d]. The intersection is nonempty because t>=a+c and t<=b+d. Thus every intermediate multiplicity is attained. This is an ordinary derived counting proposition, not a claim of separate algorithmic novelty or a machine-checked result. Marginal intervals need not be jointly realizable across different classes.

## 8. Why the observation buckets are a partition

The preceding formula relies on the fact that every trace contributes to exactly one report row.  This is not merely a convenient encoding.  If a report instead gives exact counts for arbitrary overlapping views, then even deciding whether the counts describe any selected trace set becomes NP-complete.

### Definition: OVERLAP-CONSISTENCY

An instance contains a finite token set `T`, views `V_1,...,V_m` with `V_i subseteq T`, and integers `b_i`.  The question is whether there is a subset `R subseteq T` such that `|R intersect V_i|=b_i` for every `i`.  The bit vector of `R` is a polynomial witness, so the problem is in NP.

### Theorem 5: Overlapping exact-count consistency is NP-complete

OVERLAP-CONSISTENCY is NP-complete even when every requested count is one and every token occurs in exactly three views.

*Proof.* Reduce from Exact Cover by 3-Sets (X3C).  Let the X3C ground set be `X`, where `|X|=3q`, and let `S` be a family of three-element subsets of `X`.  Create one selectable token `t_A` for every `A in S`.  For every ground element `x in X`, create the view

`V_x = {t_A : x in A}`

and require `|R intersect V_x|=1`.  Every token occurs in exactly three views because its source set has size three.  If `S'` is an exact cover, select the corresponding tokens; each element view then contains exactly one selected token.  Conversely, a compatible token selection contains exactly one set incident to every ground element.  Hence no two selected sets overlap and their union is `X`; it is an exact cover.  The construction is polynomial.  Together with membership in NP, this proves NP-completeness.  QED.

This theorem separates two contracts.  Under the partition contract, row choices are independent after one representative per required class is reserved, which yields the matching-plus-fill argument.  Under arbitrary overlap, selecting one trace simultaneously changes several equations and the independent fill step is unavailable.  The theorem does not say that every structured overlap is hard; laminar, bounded-treewidth, or otherwise restricted view families may admit specialized algorithms.  It says that the present polynomial certificate cannot be extended to unrestricted overlapping exact-count views without confronting an NP-complete consistency problem.

### Executable reduction check

`src/overlap_boundary.py` implements the X3C map and two independent tiny oracles: direct exact-cover enumeration and brute-force 0--1 view feasibility.  `tests/validate.py --part overlap` checks every subfamily of at most four of the twenty three-sets on a six-element universe for which every element occurs in at least one chosen set.  The finite check covers 4,090 locally admissible families (1,675 feasible and 2,415 infeasible) with no disagreement.  This exhaustive bounded check validates the implementation of the reduction on the named domain; it is not the proof of NP-completeness, which is the reduction above.
