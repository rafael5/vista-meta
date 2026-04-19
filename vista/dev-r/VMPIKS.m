VMPIKS ;vista-meta — PIKS heuristic classifier
 ;Spec: docs/vista-meta-spec-v0.4.md § 11.4.1
 ;RUNS IN: container, as vehu
 ;
 ;Applies deterministic heuristics to classify every FileMan file
 ;into Patient (P), Institution (I), Knowledge (K), or System (S).
 ;
 ;Usage: D RUN^VMPIKS   (writes piks.tsv + updates files.tsv)
 ;       D STATS^VMPIKS (summary only)
 ;
 Q
 ;
RUN ;Full classification run
 N RESULT,FILE,TOTAL,CLASSIFIED,TIER
 N PTARGETS  ; pointer target cache: PTARGETS(file)=list of target file#s
 N PGLOBS    ; known Patient globals
 N IGLOBS    ; known Institution globals
 N KGLOBS    ; known Knowledge globals
 N SGLOBS    ; known System globals
 ;
 W !,"VMPIKS — PIKS Heuristic Classifier",!
 W "=",$J("",40),!
 ;
 ; Initialize known global root lists (Tiers 3, H-10 through H-13)
 D INITGL(.PGLOBS,.IGLOBS,.KGLOBS,.SGLOBS)
 ;
 ; === Pass 1: Tiers 1-8 (single-pass heuristics) ===
 S TOTAL=0,CLASSIFIED=0
 S FILE=""
 F  S FILE=$O(^DD(FILE)) Q:FILE=""  Q:FILE'=+FILE  D
 . S TOTAL=TOTAL+1
 . N PIKS,METH,CONF,EVID
 . S PIKS="",METH="",CONF="",EVID=""
 . ;
 . ; --- Tier 1: Structural identity (H-01 to H-04) ---
 . D TIER1(FILE,.PIKS,.METH,.CONF,.EVID) I PIKS'="" S RESULT(FILE)=PIKS_"^"_METH_"^"_CONF_"^"_EVID,CLASSIFIED=CLASSIFIED+1 Q
 . ;
 . ; --- Tier 2: Pointer to anchor files (H-06 to H-09) ---
 . D TIER2(FILE,.PIKS,.METH,.CONF,.EVID) I PIKS'="" S RESULT(FILE)=PIKS_"^"_METH_"^"_CONF_"^"_EVID,CLASSIFIED=CLASSIFIED+1 Q
 . ;
 . ; --- Tier 3: Global root patterns (H-10 to H-13) ---
 . D TIER3(FILE,.PGLOBS,.IGLOBS,.KGLOBS,.SGLOBS,.PIKS,.METH,.CONF,.EVID) I PIKS'="" S RESULT(FILE)=PIKS_"^"_METH_"^"_CONF_"^"_EVID,CLASSIFIED=CLASSIFIED+1 Q
 . ;
 . ; --- Tier 5: Pointer topology (H-18, H-19) ---
 . D TIER5(FILE,.PIKS,.METH,.CONF,.EVID) I PIKS'="" S RESULT(FILE)=PIKS_"^"_METH_"^"_CONF_"^"_EVID,CLASSIFIED=CLASSIFIED+1 Q
 . ;
 . ; --- Tier 6: Name patterns (H-20 to H-23) ---
 . D TIER6(FILE,.PIKS,.METH,.CONF,.EVID) I PIKS'="" S RESULT(FILE)=PIKS_"^"_METH_"^"_CONF_"^"_EVID,CLASSIFIED=CLASSIFIED+1 Q
 ;
 ; === Pass 2: Tier 5 (H-05) — subfile inheritance ===
 ; Subfiles inherit parent PIKS. Overrides low-confidence classifications
 ; because a Patient subfile named "TYPE" should be P, not K.
 N INHCOUNT S INHCOUNT=0
 S FILE=""
 F  S FILE=$O(^DD(FILE)) Q:FILE=""  Q:FILE'=+FILE  D
 . ; Skip if already classified with certain or high confidence
 . I $D(RESULT(FILE)) D  Q:$P(RESULT(FILE),"^",3)="certain"  Q:$P(RESULT(FILE),"^",3)="high"
 . N PAR S PAR=$G(^DD(FILE,0,"UP"))
 . Q:PAR=""
 . ; Walk up parent chain until we find a classified parent
 . N PPIKS S PPIKS=""
 . F  Q:PAR=""  Q:PPIKS'=""  D
 . . I $D(RESULT(PAR)) S PPIKS=$P(RESULT(PAR),"^",1) Q
 . . S PAR=$G(^DD(PAR,0,"UP"))
 . I PPIKS'="" D
 . . I '$D(RESULT(FILE)) S CLASSIFIED=CLASSIFIED+1  ; new classification
 . . S RESULT(FILE)=PPIKS_"^H-05^certain^inherits from "_$$GETPAR(FILE)
 . . S INHCOUNT=INHCOUNT+1
 ;
 ; === Write piks.tsv ===
 N PATH S PATH="/home/vehu/export/normalized/piks.tsv"
 O PATH:NEWVERSION U PATH
 W "file_number",$C(9),"piks",$C(9),"piks_method",$C(9),"piks_confidence",$C(9),"piks_evidence",!
 S FILE=""
 F  S FILE=$O(RESULT(FILE)) Q:FILE=""  D
 . W FILE,$C(9)
 . W $P(RESULT(FILE),"^",1),$C(9)
 . W $P(RESULT(FILE),"^",2),$C(9)
 . W $P(RESULT(FILE),"^",3),$C(9)
 . W $P(RESULT(FILE),"^",4),!
 C PATH
 U $P W !,"Written to ",PATH,!
 ;
 ; === Stats ===
 D SHOWSTATS(.RESULT,TOTAL,CLASSIFIED,INHCOUNT)
 Q
 ;
 ; =====================================================================
 ; TIER IMPLEMENTATIONS
 ; =====================================================================
 ;
TIER1(FILE,PIKS,METH,CONF,EVID) ;Tier 1 — Structural identity
 N GL S GL=$G(^DIC(FILE,0,"GL"))
 ;
 ; H-01: Global root = ^DPT(
 I GL="^DPT(" S PIKS="P",METH="H-01",CONF="certain",EVID="global=^DPT(" Q
 ;
 ; H-02: ^DD global or file < 2
 I GL="^DD(" S PIKS="S",METH="H-02",CONF="certain",EVID="global=^DD(" Q
 I FILE<2,FILE'<0 S PIKS="S",METH="H-02",CONF="certain",EVID="file#="_FILE Q
 ;
 ; H-03: File IS file 2
 I FILE=2 S PIKS="P",METH="H-03",CONF="certain",EVID="file=2 PATIENT" Q
 ;
 ; H-04: File IS file 4
 I FILE=4 S PIKS="I",METH="H-04",CONF="certain",EVID="file=4 INSTITUTION" Q
 Q
 ;
TIER2(FILE,PIKS,METH,CONF,EVID) ;Tier 2 — Pointer to anchor files
 ; Walk fields looking for pointer targets
 N FLD,TYPE,TARG,HAS2,HAS4,HAS200,FLDNAME,EVFLD
 S FLD="",HAS2=0,HAS4=0,HAS200=0,EVFLD=""
 F  S FLD=$O(^DD(FILE,FLD)) Q:FLD=""  Q:FLD'=+FLD  D
 . Q:'$D(^DD(FILE,FLD,0))
 . S TYPE=$P(^DD(FILE,FLD,0),"^",2)
 . S FLDNAME=$P(^DD(FILE,FLD,0),"^",1)
 . ; Extract pointer target: look for Pnnn pattern
 . S TARG=$$GETPTARG(TYPE)
 . Q:TARG=""
 . I TARG=2 S HAS2=1,EVFLD=FLD_" "_FLDNAME
 . I TARG=4 S HAS4=1
 . I TARG=200 S HAS200=1
 ;
 ; H-06/H-07: Points to File 2
 I HAS2 D  Q
 . S PIKS="P",METH="H-06",CONF="high"
 . S EVID="field="_EVFLD_" points to file 2"
 ;
 ; H-08: Points to File 4 but NOT File 2
 I HAS4,'HAS2 D  Q
 . S PIKS="I",METH="H-08",CONF="high"
 . S EVID="has ptr to file 4; no ptr to file 2"
 ;
 ; H-09: Points to File 200 but NOT File 2 and NOT File 4
 I HAS200,'HAS2,'HAS4 D  Q
 . S PIKS="S",METH="H-09",CONF="high"
 . S EVID="has ptr to file 200; no ptr to file 2 or 4"
 Q
 ;
TIER3(FILE,PGLOBS,IGLOBS,KGLOBS,SGLOBS,PIKS,METH,CONF,EVID) ;Tier 3 — Global root patterns
 N GL,GNAME
 S GL=$G(^DIC(FILE,0,"GL"))
 Q:GL=""
 S GNAME=$P($P(GL,"^",2),"(",1)
 Q:GNAME=""
 ;
 ; H-10: Patient globals
 I $D(PGLOBS(GNAME)) S PIKS="P",METH="H-10",CONF="high",EVID="global="_GL_" in P-list" Q
 ;
 ; H-11: Institution globals
 I $D(IGLOBS(GNAME)) S PIKS="I",METH="H-11",CONF="high",EVID="global="_GL_" in I-list" Q
 ;
 ; H-12: Knowledge globals
 I $D(KGLOBS(GNAME)) S PIKS="K",METH="H-12",CONF="high",EVID="global="_GL_" in K-list" Q
 ;
 ; H-13: System globals
 I $D(SGLOBS(GNAME)) S PIKS="S",METH="H-13",CONF="high",EVID="global="_GL_" in S-list" Q
 Q
 ;
TIER5(FILE,PIKS,METH,CONF,EVID) ;Tier 5 — Pointer topology (H-18, H-19)
 ; H-18: pointer_in >= 10 AND pointer_out <= 2 AND no ptr to File 2
 N PTRIN,PTROUT,HAS2
 S PTRIN=$$PTRIN(FILE)
 I PTRIN<10 Q  ; not a reference table candidate
 S PTROUT=$$PTROUT(FILE,.HAS2)
 I HAS2 Q  ; points to Patient — not K
 I PTROUT>2 Q
 S PIKS="K",METH="H-18",CONF="moderate"
 S EVID="ptr_in="_PTRIN_" ptr_out="_PTROUT
 Q
 ;
TIER6(FILE,PIKS,METH,CONF,EVID) ;Tier 6 — Name patterns (H-20 to H-23)
 N FNAME S FNAME=$$GETNAME(FILE)
 S FNAME=$$UP(FNAME)
 ;
 ; H-20: Knowledge names
 I FNAME["TYPE"!(FNAME["CATEGORY")!(FNAME["CLASS")!(FNAME["CODE")!(FNAME["DEFINITION")!(FNAME["TEMPLATE")!(FNAME["REMINDER") D  Q
 . S PIKS="K",METH="H-20",CONF="low",EVID="name contains K-pattern"
 ;
 ; H-21: System names
 I FNAME["PARAMETER"!(FNAME["OPTION")!(FNAME["DEVICE")!(FNAME["ERROR")!(FNAME["TASK")!(FNAME["BULLETIN")!(FNAME["LOG")!(FNAME["AUDIT") D  Q
 . S PIKS="S",METH="H-21",CONF="low",EVID="name contains S-pattern"
 ;
 ; H-22: Institution names
 I FNAME["INSTITUTION"!(FNAME["FACILITY")!(FNAME["DIVISION")!(FNAME["WARD")!(FNAME["CLINIC")!(FNAME["SERVICE") D  Q
 . S PIKS="I",METH="H-22",CONF="low",EVID="name contains I-pattern"
 ;
 ; H-23: Patient names
 I FNAME["PATIENT"!(FNAME["VISIT")!(FNAME["ENCOUNTER")!(FNAME["ADMISSION")!(FNAME["EPISODE") D  Q
 . S PIKS="P",METH="H-23",CONF="low",EVID="name contains P-pattern"
 Q
 ;
 ; =====================================================================
 ; HELPER FUNCTIONS
 ; =====================================================================
 ;
GETPTARG(TYPE) ;Extract pointer target file# from DD type spec
 ; Type spec: "P2'" means pointer to file 2, "RP200" required ptr to 200
 ; Look for P followed by digits
 N I,C,NUM,INPTR
 S INPTR=0,NUM=""
 F I=1:1:$L(TYPE) S C=$E(TYPE,I) D  Q:NUM'=""&'INPTR
 . I C="P"!(C="p") S INPTR=1 Q
 . I INPTR,C?1N S NUM=NUM_C Q
 . I INPTR,C'?1N,NUM'="" S INPTR=0 Q  ; end of number
 . I INPTR,C'?1N S INPTR=0,NUM="" Q  ; P not followed by digit
 I NUM="" Q ""
 Q +NUM
 ;
PTRIN(FILE) ;Count files pointing TO this file (from ^DD(FILE,0,"PT"))
 N C,X S C=0,X=""
 Q:'$D(^DD(FILE,0,"PT")) 0
 F  S X=$O(^DD(FILE,0,"PT",X)) Q:X=""  S C=C+1
 Q C
 ;
PTROUT(FILE,HAS2) ;Count pointer-out fields; set HAS2 if points to file 2
 N FLD,TYPE,TARG,C
 S FLD="",C=0,HAS2=0
 F  S FLD=$O(^DD(FILE,FLD)) Q:FLD=""  Q:FLD'=+FLD  D
 . Q:'$D(^DD(FILE,FLD,0))
 . S TYPE=$P(^DD(FILE,FLD,0),"^",2)
 . S TARG=$$GETPTARG(TYPE)
 . Q:TARG=""
 . S C=C+1
 . I TARG=2 S HAS2=1
 Q C
 ;
GETNAME(FILE) ;Get file name
 I $D(^DIC(FILE,0)) Q $P(^DIC(FILE,0),"^",1)
 Q $P($G(^DD(FILE,0)),"^",1)
 ;
GETPAR(FILE) ;Get parent file
 Q $G(^DD(FILE,0,"UP"))
 ;
UP(S) ;Uppercase
 Q $TR(S,"abcdefghijklmnopqrstuvwxyz","ABCDEFGHIJKLMNOPQRSTUVWXYZ")
 ;
INITGL(PG,IG,KG,SG) ;Initialize known global root lists
 ; H-10: Patient globals
 S PG("DPT")="",PG("LR")="",PG("GMR")="",PG("GMRD")=""
 S PG("TIU")="",PG("OR")="",PG("SRF")="",PG("SRU")=""
 S PG("AUPNVSIT")="",PG("AUPNVCPT")="",PG("AUPNVPRV")=""
 S PG("AUPNVPOV")="",PG("AUPNVHF")="",PG("AUPNVIMM")=""
 S PG("DGPM")="",PG("DGM")="",PG("DGP")=""
 S PG("SCE")="",PG("SDV")=""
 S PG("PSRX")="",PG("PSB")=""
 S PG("DVB")="",PG("NUR")=""
 S PG("RADPT")="",PG("RAR")=""
 S PG("FH")="",PG("FHN")="",PG("FHNU")=""
 ;
 ; H-11: Institution globals
 S IG("SC")="",IG("DG")=""
 ;
 ; H-12: Knowledge globals
 S KG("ICD9")="",KG("ICD0")="",KG("ICPT")="",KG("ICD")=""
 S KG("LEX")="",KG("PSDRUG")="",KG("PSD")=""
 S KG("AUTTHF")="",KG("AUTTLOC")=""
 S KG("LAM")="",KG("PSR")=""
 S KG("PSNDF")="",KG("PSN")=""
 S KG("ORD")="",KG("ORP")=""
 S KG("ETSRXN")=""
 ;
 ; H-13: System globals
 S SG("XTV")="",SG("XMB")="",SG("XUS")=""
 S SG("DIC")="",SG("DD")="",SG("DI")=""
 S SG("DIE")="",SG("DIA")="",SG("DIPT")="",SG("DIB")=""
 S SG("DDD")="",SG("DDE")=""
 S SG("XPD")="",SG("XT")=""
 S SG("VA")=""
 Q
 ;
SHOWSTATS(RESULT,TOTAL,CLASSIFIED,INHCOUNT) ;Display classification stats
 N P,I,K,S,U,FILE,PIKS
 N CERTAIN,HIGH,MODERATE,LOW
 S P=0,I=0,K=0,S=0,U=TOTAL-CLASSIFIED
 S CERTAIN=0,HIGH=0,MODERATE=0,LOW=0
 S FILE=""
 F  S FILE=$O(RESULT(FILE)) Q:FILE=""  D
 . S PIKS=$P(RESULT(FILE),"^",1)
 . I PIKS="P" S P=P+1
 . I PIKS="I" S I=I+1
 . I PIKS="K" S K=K+1
 . I PIKS="S" S S=S+1
 . N CNF S CNF=$P(RESULT(FILE),"^",3)
 . I CNF="certain" S CERTAIN=CERTAIN+1
 . I CNF="high" S HIGH=HIGH+1
 . I CNF="moderate" S MODERATE=MODERATE+1
 . I CNF="low" S LOW=LOW+1
 ;
 W !,"VMPIKS Classification Results",!
 W "=",$J("",40),!
 W "  Total files:      ",TOTAL,!
 W "  Classified:       ",CLASSIFIED," (",$FN(CLASSIFIED/TOTAL*100,"",1),"%)",!
 W "    Inherited (H-05): ",INHCOUNT,!
 W "  Unclassified:     ",U," (",$FN(U/TOTAL*100,"",1),"%)",!
 W !
 W "  By category:",!
 W "    P (Patient):      ",P," (",$FN(P/TOTAL*100,"",1),"%)",!
 W "    I (Institution):  ",I," (",$FN(I/TOTAL*100,"",1),"%)",!
 W "    K (Knowledge):    ",K," (",$FN(K/TOTAL*100,"",1),"%)",!
 W "    S (System):       ",S," (",$FN(S/TOTAL*100,"",1),"%)",!
 W !
 W "  By confidence:",!
 W "    Certain:   ",CERTAIN,!
 W "    High:      ",HIGH,!
 W "    Moderate:  ",MODERATE,!
 W "    Low:       ",LOW,!
 ;
 ; Show top heuristics by hit count
 W !,"  By heuristic:",!
 N HCNT,H
 S FILE="" F  S FILE=$O(RESULT(FILE)) Q:FILE=""  D
 . S H=$P(RESULT(FILE),"^",2)
 . S HCNT(H)=$G(HCNT(H))+1
 S H="" F  S H=$O(HCNT(H)) Q:H=""  W "    ",H,$J("",10-$L(H)),$J(HCNT(H),6)," files",!
 Q
