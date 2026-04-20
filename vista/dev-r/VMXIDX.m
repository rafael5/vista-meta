VMXIDX ;vista-meta — XINDEX driver per XINDX7 programmatic contract
 ;Spec: docs/vista-meta-spec-v0.4.md § 11
 ;Reference: docs/xindex-reference.md
 ;RUNS IN: container, as vehu
 ;
 ;Documented contract from XINDX7 header:
 ;   To call XINDEX from elsewhere:
 ;     D SETUP^XINDX7
 ;     Load routines into ^UTILITY($J,1,<rtn name>,0,n,0)
 ;       with @root@(0)='line count' and @root@(n,0)=a routine line
 ;     For each routine S RTN="rtn name",INDLC=0 D BEG^XINDEX
 ;
 ;This wrapper follows that contract exactly, bypassing LOAD1's
 ;`ZL @X` indirection (which has YDB quirks in this VEHU).
 ;
 ;After all routines processed, D FINISH writes results to File 9.8.
 ;
 Q
 ;
SETUP ;one-time XINDEX environment setup
 ;Pre-fill device and header vars — VEHU lacks ^%ZIS / partial ^%ZOSF.
 S IO=$P,IOM=80,IOSL=24,IOF="!"
 S INDXDT=$H,INDDA=0
 S INDHDR="VMXIDX BATCH"
 S INDHDR(1)="UCI: VMXIDX  CPU: ROU  "_$H
 S INDHDR(2)="vista-meta XINDEX bake"
 ;INP parameters for full-fidelity capture (INP(7)=1 = save to File 9.8)
 S INP(1)=0,INP(2)=0,INP(3)=0,INP(4)=1,INP(5)="R",INP(6)=1
 S INP(7)=1,INP(8)=0,INP(9)=0,INP(10)=""
 S INP(11)="",INP(12)=""
 S INP("MAX")=20000,INP("CMAX")=15000
 S DUZ=.5
 ;call SETUP^XINDX7's BUILD to populate error tables etc.
 D BUILD^XINDX7
 ;header vars used by downstream code
 S Q="""",U="^",INDDS=0,IND("TM")=$H
 Q
 ;
LOAD1R(RTN,LC) ;Load source of routine RTN into ^UTILITY($J,1,RTN,0,...)
 ;Returns LC = line count, or 0 if routine can't be linked.
 N LN,X,$ETRAP
 S LC=0
 S $ETRAP="S $ECODE="""" Q"
 ;YDB requires quoted-string expression indirection for ZL with var.
 ;Form ZL @(""""_RTN_"""") expands to ZL "<rtn>".
 ZL @(""""_RTN_"""")
 S $ETRAP=""
 K ^UTILITY($J,1,RTN,0)
 F LN=1:1 S $ETRAP="S $ECODE="""" Q" S X=$T(@("+"_LN_"^"_RTN)) S $ETRAP="" Q:X=""  S ^UTILITY($J,1,RTN,0,LN,0)=X,LC=LN
 S ^UTILITY($J,1,RTN,0,0)=LC
 Q
 ;
PROC(RTN) ;Process one routine end-to-end
 ;Returns 1 on success, 0 on skip
 N LC,$ETRAP
 S $ETRAP="S $ECODE="""" Q"
 D LOAD1R(RTN,.LC)
 I LC'>0 Q 0
 ;RSUM checksum (copy what LOAD1 does)
 S ^UTILITY($J,1,RTN,"RSUM")="B"_$$SUMB^XPDRSUM($NA(^UTILITY($J,1,RTN,0)))
 ;set per-routine state that BEG^XINDEX reads
 S INDLC=0
 D BEG^XINDEX
 Q 1
 ;
SAMPLE(N) ;run XINDEX on N routines (testing)
 N IEN,Z,NAME,TYP,OK,FAIL,STARTED,ELAPSED,R
 I '$D(N) S N=5
 S STARTED=$H
 W !,"VMXIDX SAMPLE run (N=",N,")",!
 K ^UTILITY($J)
 D SETUP
 S (IEN,OK,FAIL)=0
 F  S IEN=$O(^DIC(9.8,IEN)) Q:IEN'>0!((OK+FAIL)'<N)  D
 . S Z=$G(^DIC(9.8,IEN,0)) Q:Z=""
 . S NAME=$P(Z,"^",1),TYP=$P(Z,"^",2) Q:TYP'="R"&(TYP'="")
 . S R=$$PROC(NAME) I R S OK=OK+1 Q
 . S FAIL=FAIL+1
 S ELAPSED=$$HDIFF(STARTED,$H)
 W !,"  Succeeded: ",OK,"  Failed: ",FAIL
 W !,"  Elapsed: ",ELAPSED," sec",!
 D DIAGSCRATCH
 D EXTRACT
 Q
 ;
DIAGSCRATCH ;Dump what's in ^UTILITY($J,1,...) — scratch state after a run
 N R,K,CE,CT,CX,CG,CL
 S R=""
 W "  scratch-global state:",!
 F  S R=$O(^UTILITY($J,1,R)) Q:R=""  D
 . S K=$G(^UTILITY($J,1,R,0,0))
 . S CE=$G(^UTILITY($J,1,R,"E",0))+0
 . S CT=0,CX=0,CG=0,CL=0
 . N S S S=""
 . F  S S=$O(^UTILITY($J,1,R,"T",S)) Q:S=""  S CT=CT+1
 . S S=""
 . F  S S=$O(^UTILITY($J,1,R,"X",S)) Q:S=""  S CX=CX+1
 . S S=""
 . F  S S=$O(^UTILITY($J,1,"***","G",S,R_" ")) Q:S=""
 . W "    ",R,": lines=",K," errs=",CE," tags=",CT," xref=",CX,!
 Q
 ;
ALL ;run XINDEX on all type=R routines in File 9.8
 N IEN,Z,NAME,TYP,OK,FAIL,STARTED,ELAPSED,R
 S STARTED=$H
 W !,"VMXIDX FULL run starting ($H=",$H,")",!
 K ^UTILITY($J)
 D SETUP
 S (IEN,OK,FAIL)=0
 F  S IEN=$O(^DIC(9.8,IEN)) Q:IEN'>0  D
 . S Z=$G(^DIC(9.8,IEN,0)) Q:Z=""
 . S NAME=$P(Z,"^",1),TYP=$P(Z,"^",2) Q:TYP'="R"&(TYP'="")
 . S R=$$PROC(NAME) I R S OK=OK+1 Q
 . S FAIL=FAIL+1
 . ;progress ticker every 500 routines
 . I (OK+FAIL)#500=0 W "  ",OK+FAIL," done (",OK," ok, ",FAIL," fail)...",!
 S ELAPSED=$$HDIFF(STARTED,$H)
 W !,"  Succeeded: ",OK,"  Failed: ",FAIL
 W !,"  Elapsed: ",ELAPSED," sec (",ELAPSED/60," min)",!
 D EXTRACT
 Q
 ;
FINISH ;After all PROC calls, drive ^XINDX5 to finalize + write File 9.8
 ;XINDX5 does cross-reference validation and (if INP(7)) writes 9.8
 N RN,RTN S RN="$",RTN="$"
 D ^XINDX5
 Q
 ;
EXTRACT ;Write scratch-global contents to /tmp TSV files
 ;Outputs:
 ;  /tmp/xindex-routines.tsv   one row per processed routine
 ;  /tmp/xindex-errors.tsv     one row per error instance
 ;  /tmp/xindex-xrefs.tsv      one row per external routine reference
 ;  /tmp/xindex-tags.tsv       one row per tag/label
 N R,T,S,E,N,DATA,LINE,LC,EC,ERTX,LAB,SEV,MSG,TAB,PA,PB,PC,PD
 S TAB=$C(9)
 ;---- routines summary ----
 S PA="/tmp/xindex-routines.tsv"
 O PA:NEWVERSION U PA
 W "routine",TAB,"line_count",TAB,"tag_count",TAB,"xref_count",TAB,"error_count",TAB,"rsum_value",!
 S R=""
 F  S R=$O(^UTILITY($J,1,R)) Q:R=""  D
 . S LC=$G(^UTILITY($J,1,R,0,0))
 . S EC=+$G(^UTILITY($J,1,R,"E",0))
 . N T S T=0,S=""
 . F  S S=$O(^UTILITY($J,1,R,"T",S)) Q:S=""  S T=T+1
 . N X S X=0,S=""
 . F  S S=$O(^UTILITY($J,1,R,"X",S)) Q:S=""  S X=X+1
 . W R,TAB,LC,TAB,T,TAB,X,TAB,EC,TAB,$G(^UTILITY($J,1,R,"RSUM")),!
 C PA
 ;---- errors detail ----
 S PB="/tmp/xindex-errors.tsv"
 O PB:NEWVERSION U PB
 W "routine",TAB,"entry_index",TAB,"line_text",TAB,"tag_offset",TAB,"error_text",!
 S R=""
 F  S R=$O(^UTILITY($J,1,R)) Q:R=""  D
 . S EC=+$G(^UTILITY($J,1,R,"E",0)) Q:EC<1
 . F N=1:1:EC S DATA=$G(^UTILITY($J,1,R,"E",N)) Q:DATA=""  D
 . . S LINE=$P(DATA,TAB,1)
 . . S LAB=$P(DATA,TAB,2)
 . . S ERTX=$P(DATA,TAB,3,999)
 . . W R,TAB,N,TAB,LINE,TAB,LAB,TAB,ERTX,!
 C PB
 ;---- external references (XINDEX's call graph) ----
 S PC="/tmp/xindex-xrefs.tsv"
 O PC:NEWVERSION U PC
 W "routine",TAB,"ref",TAB,"location_list",!
 S R=""
 F  S R=$O(^UTILITY($J,1,R)) Q:R=""  D
 . S S=""
 . F  S S=$O(^UTILITY($J,1,R,"X",S)) Q:S=""  D
 . . N L,LL S LL="",L=""
 . . F  S L=$O(^UTILITY($J,1,R,"X",S,L)) Q:L=""  S LL=LL_$S(LL]"":",",1:"")_L
 . . W R,TAB,S,TAB,LL,!
 C PC
 ;---- tags (labels) ----
 S PD="/tmp/xindex-tags.tsv"
 O PD:NEWVERSION U PD
 W "routine",TAB,"tag",TAB,"data",!
 S R=""
 F  S R=$O(^UTILITY($J,1,R)) Q:R=""  D
 . S S=""
 . F  S S=$O(^UTILITY($J,1,R,"T",S)) Q:S=""  D
 . . W R,TAB,S,TAB,$G(^UTILITY($J,1,R,"T",S)),!
 C PD
 U $P
 W !,"Extracted: /tmp/xindex-{routines,errors,xrefs,tags}.tsv",!
 Q
 ;
HDIFF(H1,H2) ;seconds between two $H values
 N D1,S1,D2,S2
 S D1=$P(H1,","),S1=$P(H1,",",2)
 S D2=$P(H2,","),S2=$P(H2,",",2)
 Q (D2-D1)*86400+(S2-S1)
 ;
