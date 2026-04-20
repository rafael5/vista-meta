VMDUMP98 ;vista-meta — extract File 9.8 (ROUTINE) to TSV
 ;Spec: docs/vista-meta-spec-v0.4.md § 11
 ;ADR-045 Phase 4a: authoritative routine metadata from VistA itself.
 ;RUNS IN: container, as vehu
 ;
 ;File 9.8 is VistA's self-inventory of routines. One row per entry.
 ;Cross-references against MANIFEST.tsv (Dockerfile build) to resolve
 ;the +1/+8 divergence flagged in TODO.md T-001.
 ;
 ;Storage map (from ^DD(9.8,<field>,0)):
 ;  .01 NAME            → ^DIC(9.8,N,0) piece 1
 ;  1   TYPE            → ^DIC(9.8,N,0) piece 2 (P=PACKAGE, R=ROUTINE)
 ;  1.2 SIZE (BYTES)    → ^DIC(9.8,N,0) piece 3
 ;  1.5 RSUM VALUE      → ^DIC(9.8,N,0) piece 5
 ;  7.2 CHECKSUM VALUE  → ^DIC(9.8,N,4) piece 2
 ;
 ;Usage: D RUN^VMDUMP98    (writes vista-file-9-8.tsv to /tmp, copy out via
 ;                          `make dump-file-9-8`)
 ;       D TSV^VMDUMP98    (TSV to stdout)
 ;       D STATS^VMDUMP98  (summary counts)
 ;
 ;Output path is /tmp because vehu doesn't own the bind-mounted
 ;/home/vehu/export tree (it's ubuntu-owned from the host side). The
 ;Makefile target docker-cps the file out to vista/export/code-model/.
 ;
 Q
 ;
RUN ;Write vista-file-9-8.tsv to /tmp
 N PATH S PATH="/tmp/vista-file-9-8.tsv"
 O PATH:NEWVERSION U PATH
 D TSV
 C PATH
 W !,"Written: ",PATH,!
 D STATS
 Q
 ;
TSV ;Emit TSV to current device
 N IEN,ZERO,SUB4,NAME,TYP,SIZ,RSUM,CKSM,T
 S T=$C(9)
 W "ien",T,"name",T,"type",T,"size_bytes",T,"rsum_value",T,"checksum_value",!
 S IEN=0
 F  S IEN=$O(^DIC(9.8,IEN)) Q:IEN'>0  D
 . S ZERO=$G(^DIC(9.8,IEN,0))
 . Q:ZERO=""
 . S NAME=$P(ZERO,"^",1)
 . S TYP=$P(ZERO,"^",2)
 . S SIZ=$P(ZERO,"^",3)
 . S RSUM=$P(ZERO,"^",5)
 . S SUB4=$G(^DIC(9.8,IEN,4))
 . S CKSM=$P(SUB4,"^",2)
 . W IEN,T,NAME,T,TYP,T,SIZ,T,RSUM,T,CKSM,!
 Q
 ;
STATS ;Print summary counts to current device
 N IEN,ZERO,TYP,TOTAL,ROU,PKG,OTHER
 S (TOTAL,ROU,PKG,OTHER)=0
 S IEN=0
 F  S IEN=$O(^DIC(9.8,IEN)) Q:IEN'>0  D
 . S ZERO=$G(^DIC(9.8,IEN,0))
 . Q:ZERO=""
 . S TOTAL=TOTAL+1
 . S TYP=$P(ZERO,"^",2)
 . I TYP="R" S ROU=ROU+1 Q
 . I TYP="P" S PKG=PKG+1 Q
 . S OTHER=OTHER+1
 W !,"File 9.8 entry counts:"
 W !,"  total:  ",TOTAL
 W !,"  type=R: ",ROU,"  (routines)"
 W !,"  type=P: ",PKG,"  (package markers)"
 W !,"  other:  ",OTHER,!
 Q
 ;
