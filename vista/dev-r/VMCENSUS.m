VMCENSUS ;vista-meta global census — Phase 1 recon
 ;Spec: docs/vista-meta-spec-v0.4.md § 11.4.4
 ;RUNS IN: container, as vehu
 ;
 ;Phase 1 recon: enumerate all globals, match against ^DIC,
 ;report FileMan vs non-FileMan split.
 ;
 ;Usage: D RECON^VMCENSUS  (requires GLIST built first by shell wrapper)
 ;  or:  vista/scripts/vmcensus.sh  (recommended — handles everything)
 ;
 Q
 ;
RECON ;Phase 1 recon — reads global list from ^TMP("VMCENSUS",$J)
 ;Caller must populate ^TMP("VMCENSUS",$J,globalname)="" first
 N TOTAL,FM,NONFM,SCRATCH,GNAME
 N FMDATA,NFMDATA,SCRDATA
 N DICFILE,DICNAME,COUNT,PREFIX
 ;
 ; Build ^DIC global-root index
 N DICIDX D BLDIDX(.DICIDX)
 ;
 S TOTAL=0,FM=0,NONFM=0,SCRATCH=0
 S GNAME=""
 F  S GNAME=$O(^TMP("VMCENSUS",$J,GNAME)) Q:GNAME=""  D
 . S TOTAL=TOTAL+1
 . ;
 . ; Scratch/temp
 . I GNAME?1"TMP".E!(GNAME?1"UTILITY".E)!(GNAME?1"XTMP".E) D  Q
 . . S SCRATCH=SCRATCH+1
 . . S COUNT=$$CNT1(GNAME)
 . . S SCRDATA(GNAME)=COUNT
 . ;
 . ; Check ^DIC
 . S DICFILE=$$FINDIC("^"_GNAME_"(",.DICIDX)
 . I DICFILE'="" D  Q
 . . S FM=FM+1
 . . S COUNT=$$CNT1(GNAME)
 . . S DICNAME=$P($G(^DIC(DICFILE,0)),"^",1)
 . . S FMDATA(GNAME)=DICFILE_"^"_DICNAME_"^"_COUNT
 . ;
 . S NONFM=NONFM+1
 . S COUNT=$$CNT1(GNAME)
 . S PREFIX=$E(GNAME,1,3)
 . S NFMDATA(GNAME)=COUNT_"^"_PREFIX
 ;
 ; === Output ===
 W !,"VMCENSUS Phase 1 Recon",!
 W !,"Summary:",!
 W "  Total globals:         ",TOTAL,!
 W "  FileMan (^DIC match):  ",FM,!
 W "  Non-FileMan:           ",NONFM,!
 W "  Scratch/temp:          ",SCRATCH,!
 ;
 ; Non-FM by prefix
 W !,"Non-FileMan by prefix:",!
 N PFXCNT,PFXNODES,PFX
 S GNAME="" F  S GNAME=$O(NFMDATA(GNAME)) Q:GNAME=""  D
 . S PFX=$P(NFMDATA(GNAME),"^",2)
 . S PFXCNT(PFX)=$G(PFXCNT(PFX))+1
 . S PFXNODES(PFX)=$G(PFXNODES(PFX))+$P(NFMDATA(GNAME),"^",1)
 S PFX="" F  S PFX=$O(PFXCNT(PFX)) Q:PFX=""  D
 . W "  ",PFX,$J("",6-$L(PFX)),$J(PFXCNT(PFX),4)," globals",$J(PFXNODES(PFX),10)," nodes",!
 ;
 ; Top 20 non-FM by size
 W !,"Top 20 non-FM globals:",!
 N TOPG,I,SKEY
 S GNAME="" F  S GNAME=$O(NFMDATA(GNAME)) Q:GNAME=""  D
 . S COUNT=$P(NFMDATA(GNAME),"^",1)
 . S TOPG(10000000-COUNT,GNAME)=""
 S I=0,SKEY=""
 F  S SKEY=$O(TOPG(SKEY)) Q:SKEY=""!(I>19)  D
 . N G2 S G2=""
 . F  S G2=$O(TOPG(SKEY,G2)) Q:G2=""!(I>19)  D
 . . S I=I+1,COUNT=10000000-SKEY
 . . N ISDFN S ISDFN=$$CHKDFN(G2)
 . . W "  ",$J(I,3),". ^",G2
 . . W ?28,$J(COUNT,10)," nodes  DFN=",ISDFN,!
 ;
 ; Scratch
 W !,"Scratch globals (excluded):",!
 S GNAME="" F  S GNAME=$O(SCRDATA(GNAME)) Q:GNAME=""  D
 . W "  ^",GNAME,$J(SCRDATA(GNAME),10)," nodes",!
 ;
 W !,"Done.",!
 Q
 ;
BLDIDX(IDX) ;Build ^DIC global-root -> file# index
 ; Global root is at ^DIC(file,0,"GL"), e.g., "^DPT(" for file 2
 N F,GR
 S F="" F  S F=$O(^DIC(F)) Q:F=""  D
 . Q:'$D(^DIC(F,0))
 . S GR=$G(^DIC(F,0,"GL"))
 . Q:GR=""
 . ; Extract just the global name (strip ^ and ()
 . N GNAME S GNAME=$P($P(GR,"^",2),"(",1)
 . Q:GNAME=""
 . S IDX(GNAME)=F
 Q
 ;
FINDIC(GREF,IDX) ;Find ^DIC file# for global name
 ; GREF is "^GNAME(" — extract GNAME and look up in index
 N GNAME S GNAME=$P($P(GREF,"^",2),"(",1)
 I $D(IDX(GNAME)) Q IDX(GNAME)
 Q ""
 ;
CNT1(GNAME) ;Count first-level subscripts (cap at 999999)
 N S,C S S="",C=0
 F  S S=$O(@("^"_GNAME_"(S)")) Q:S=""  S C=C+1 Q:C>999999
 Q C
 ;
CHKDFN(GNAME) ;Check if first subscripts are DPT IENs
 N S,M,T,I S S="",M=0,T=0
 F I=1:1:5 S S=$O(@("^"_GNAME_"(S)")) Q:S=""  D
 . S T=T+1
 . I S?1.N,$D(^DPT(+S)) S M=M+1
 I T=0 Q "N/A"
 I M/T>.6 Q "YES"
 Q "NO"
