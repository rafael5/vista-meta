VMDUMP19 ;vista-meta — extract File 19 (OPTION) to TSV
 ;Spec: docs/vista-meta-spec-v0.4.md § 11
 ;ADR-045 Phase 4c: authoritative menu/option registry.
 ;RUNS IN: container, as vehu
 ;
 ;File 19 is VistA's menu system — every option, menu, action, and
 ;broker endpoint. The TYPE field (4) is the role signal: A=action,
 ;M=menu, R=run-routine, B=broker, S=server, O=protocol, etc. The
 ;ROUTINE field (25) links options typed R/A/etc. to the routine
 ;that implements them (may be in "TAG^ROUTINE" format).
 ;
 ;Global root: ^DIC(19,...)
 ;
 ;Storage map (from ^DD(19,<field>,0)):
 ;  .01 NAME         → 0;1
 ;  1   MENU TEXT    → 0;2
 ;  4   TYPE         → 0;4   set of A/E/I/M/P/R/O/Q/X/S/L/C/W/Z/B
 ;  12  PACKAGE      → 0;12  pointer to ^DIC(9.4,...)
 ;  25  ROUTINE      → 25;E1,245  may be "TAG^ROUTINE" or "ROUTINE"
 ;
 ;Usage: D RUN^VMDUMP19  (writes /tmp/options.tsv)
 ;       D TSV^VMDUMP19  (TSV to stdout)
 ;       D STATS^VMDUMP19
 ;
 Q
 ;
RUN ;Write options.tsv to /tmp
 N PATH S PATH="/tmp/options.tsv"
 O PATH:NEWVERSION U PATH
 D TSV
 C PATH
 W !,"Written: ",PATH,!
 D STATS
 Q
 ;
TSV ;Emit TSV to current device
 N IEN,Z,RTN,NAME,MTEXT,TYP,PKGIEN,PKGNAME,TAG,ROU,T
 S T=$C(9)
 W "ien",T,"name",T,"menu_text",T,"type",T,"package",T,"routine_raw",T,"tag",T,"routine",!
 S IEN=0
 F  S IEN=$O(^DIC(19,IEN)) Q:IEN'>0  D
 . S Z=$G(^DIC(19,IEN,0))
 . Q:Z=""
 . S NAME=$P(Z,"^",1)
 . S MTEXT=$P(Z,"^",2)
 . S TYP=$P(Z,"^",4)
 . S PKGIEN=$P(Z,"^",12)
 . S PKGNAME=""
 . I PKGIEN'="" S PKGNAME=$P($G(^DIC(9.4,PKGIEN,0)),"^",1)
 . S RTN=$G(^DIC(19,IEN,25))
 . I RTN["^" S TAG=$P(RTN,"^",1),ROU=$P(RTN,"^",2)
 . E  S TAG="",ROU=RTN
 . ;strip TSV-breaking chars from menu text (rare)
 . S MTEXT=$TR(MTEXT,$C(9,10,13)," ")
 . W IEN,T,NAME,T,MTEXT,T,TYP,T,PKGNAME,T,RTN,T,TAG,T,ROU,!
 Q
 ;
STATS ;Summary counts
 N IEN,Z,TYP,TOT,WITHROU,BYTYPE
 S TOT=0,WITHROU=0
 S IEN=0
 F  S IEN=$O(^DIC(19,IEN)) Q:IEN'>0  D
 . S Z=$G(^DIC(19,IEN,0))
 . Q:Z=""
 . S TOT=TOT+1
 . S TYP=$P(Z,"^",4)
 . I TYP="" S TYP="(empty)"
 . S BYTYPE(TYP)=$G(BYTYPE(TYP))+1
 . I $G(^DIC(19,IEN,25))'="" S WITHROU=WITHROU+1
 W !,"File 19 (OPTION) counts:"
 W !,"  total:              ",TOT
 W !,"  with routine (25):  ",WITHROU
 W !,"  by TYPE:"
 N K S K=""
 F  S K=$O(BYTYPE(K)) Q:K=""  W !,"    ",$J(K,8)," : ",BYTYPE(K)
 W !
 Q
 ;
