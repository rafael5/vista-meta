VMDUMP101 ;vista-meta — extract File 101 (PROTOCOL) to TSV
 ;Spec: docs/vista-meta-spec-v0.4.md § 11
 ;ADR-045 Phase 4d: authoritative protocol / event-driver registry.
 ;RUNS IN: container, as vehu
 ;
 ;File 101 is VistA's protocol system — used by CPRS, Order Entry,
 ;HL7, and ScreenMan for event-driven and extensible menu actions.
 ;Unlike File 19 (which has a dedicated ROUTINE field), File 101
 ;invokes code via ENTRY ACTION (MUMPS text). Parsing routine refs
 ;out of ENTRY ACTION is Phase 5 (call-graph) — this phase captures
 ;the raw text.
 ;
 ;Global root: ^ORD(101,...)
 ;
 ;Storage map (from ^DD(101,<field>,0)):
 ;  .01 NAME          → 0;1
 ;  1   ITEM TEXT     → 0;2
 ;  4   TYPE          → 0;4  (A/M/O/Q/L/X/D/T/E/S)
 ;  12  PACKAGE       → 0;12 (pointer to ^DIC(9.4,...))
 ;  20  ENTRY ACTION  → 20;E1,245  (MUMPS code, 245-char max)
 ;  15  EXIT ACTION   → 15;E1,245
 ;
 ;TYPE semantics (per DD):
 ;  A=action, M=menu, O=protocol, Q=protocol menu, L=limited protocol,
 ;  X=extended action, D=dialog, T=term, E=event driver, S=subscriber
 ;
 ;Usage: D RUN^VMDUMP101  (writes /tmp/protocols.tsv)
 ;       D TSV^VMDUMP101  (TSV to stdout)
 ;       D STATS^VMDUMP101
 ;
 Q
 ;
RUN ;Write protocols.tsv to /tmp
 N PATH S PATH="/tmp/protocols.tsv"
 O PATH:NEWVERSION U PATH
 D TSV
 C PATH
 W !,"Written: ",PATH,!
 D STATS
 Q
 ;
TSV ;Emit TSV to current device
 N IEN,Z,NAME,ITEM,TYP,PKGIEN,PKGNAME,ENTRY,EXIT,T
 S T=$C(9)
 W "ien",T,"name",T,"item_text",T,"type",T,"package",T,"entry_action",T,"exit_action",!
 S IEN=0
 F  S IEN=$O(^ORD(101,IEN)) Q:IEN'>0  D
 . S Z=$G(^ORD(101,IEN,0))
 . Q:Z=""
 . S NAME=$P(Z,"^",1)
 . S ITEM=$P(Z,"^",2)
 . S TYP=$P(Z,"^",4)
 . S PKGIEN=$P(Z,"^",12)
 . S PKGNAME=""
 . I PKGIEN'="" S PKGNAME=$P($G(^DIC(9.4,PKGIEN,0)),"^",1)
 . S ENTRY=$G(^ORD(101,IEN,20))
 . S EXIT=$G(^ORD(101,IEN,15))
 . ;Strip TSV-breakers from free-text fields.
 . S ITEM=$TR(ITEM,$C(9,10,13)," ")
 . S ENTRY=$TR(ENTRY,$C(9,10,13)," ")
 . S EXIT=$TR(EXIT,$C(9,10,13)," ")
 . W IEN,T,NAME,T,ITEM,T,TYP,T,PKGNAME,T,ENTRY,T,EXIT,!
 Q
 ;
STATS ;Summary counts
 N IEN,Z,TYP,TOT,WITHENTRY,WITHPKG,BYTYPE
 S (TOT,WITHENTRY,WITHPKG)=0
 S IEN=0
 F  S IEN=$O(^ORD(101,IEN)) Q:IEN'>0  D
 . S Z=$G(^ORD(101,IEN,0))
 . Q:Z=""
 . S TOT=TOT+1
 . S TYP=$P(Z,"^",4)
 . I TYP="" S TYP="(empty)"
 . S BYTYPE(TYP)=$G(BYTYPE(TYP))+1
 . I $G(^ORD(101,IEN,20))'="" S WITHENTRY=WITHENTRY+1
 . I $P(Z,"^",12)'="" S WITHPKG=WITHPKG+1
 W !,"File 101 (PROTOCOL) counts:"
 W !,"  total:               ",TOT
 W !,"  with entry action:   ",WITHENTRY
 W !,"  with package:        ",WITHPKG
 W !,"  by TYPE:"
 N K S K=""
 F  S K=$O(BYTYPE(K)) Q:K=""  W !,"    ",$J(K,8)," : ",BYTYPE(K)
 W !
 Q
 ;
