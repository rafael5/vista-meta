VMDUMP8994 ;vista-meta — extract File 8994 (REMOTE PROCEDURE) to TSV
 ;Spec: docs/vista-meta-spec-v0.4.md § 11
 ;ADR-045 Phase 4b: authoritative RPC registry.
 ;RUNS IN: container, as vehu
 ;
 ;File 8994 is the RPC Broker's registry — every procedure that can
 ;be invoked remotely (typically by CPRS, delphi clients) by a
 ;TAG^ROUTINE reference. Authoritative role signal: a routine listed
 ;in the ROUTINE (.03) field here IS an RPC entry point.
 ;
 ;Global root: ^XWB(8994,...)  (not ^DIC)
 ;
 ;Storage map (from ^DD(8994,<field>,0)):
 ;  .01 NAME              → 0;1
 ;  .02 TAG               → 0;2
 ;  .03 ROUTINE           → 0;3
 ;  .04 RETURN VALUE TYPE → 0;4  (1=SINGLE,2=ARRAY,3=WORD-PROC,4=GLOBAL-ARRAY,5=GLOBAL-INSTANCE)
 ;  .05 AVAILABILITY      → 0;5  (P=PUBLIC,S=SUBSCRIPTION,A=AGREEMENT,R=RESTRICTED)
 ;  .06 INACTIVE          → 0;6  (0=ACTIVE,1=INACTIVE,2=LOCAL-INACTIVE,3=REMOTE-INACTIVE)
 ;  .09 VERSION           → 0;9
 ;
 ;Usage: D RUN^VMDUMP8994  (writes /tmp/rpcs.tsv, docker-cp'd out by Makefile)
 ;       D TSV^VMDUMP8994  (TSV to stdout)
 ;       D STATS^VMDUMP8994
 ;
 Q
 ;
RUN ;Write rpcs.tsv to /tmp
 N PATH S PATH="/tmp/rpcs.tsv"
 O PATH:NEWVERSION U PATH
 D TSV
 C PATH
 W !,"Written: ",PATH,!
 D STATS
 Q
 ;
TSV ;Emit TSV to current device
 N IEN,Z,NAME,TAG,ROU,RET,AVAIL,INACT,VER,T
 S T=$C(9)
 W "ien",T,"name",T,"tag",T,"routine",T,"return_type",T,"availability",T,"inactive",T,"version",!
 S IEN=0
 F  S IEN=$O(^XWB(8994,IEN)) Q:IEN'>0  D
 . S Z=$G(^XWB(8994,IEN,0))
 . Q:Z=""
 . S NAME=$P(Z,"^",1)
 . S TAG=$P(Z,"^",2)
 . S ROU=$P(Z,"^",3)
 . S RET=$P(Z,"^",4)
 . S AVAIL=$P(Z,"^",5)
 . S INACT=$P(Z,"^",6)
 . S VER=$P(Z,"^",9)
 . W IEN,T,NAME,T,TAG,T,ROU,T,RET,T,AVAIL,T,INACT,T,VER,!
 Q
 ;
STATS ;Summary counts
 N IEN,Z,TOT,ACTIVE,INACTIVE,PUB,SUBS,AGRE,RESTR,NOROU
 S (TOT,ACTIVE,INACTIVE,PUB,SUBS,AGRE,RESTR,NOROU)=0
 S IEN=0
 F  S IEN=$O(^XWB(8994,IEN)) Q:IEN'>0  D
 . S Z=$G(^XWB(8994,IEN,0))
 . Q:Z=""
 . S TOT=TOT+1
 . S I=$P(Z,"^",6) I I="0"!(I="") S ACTIVE=ACTIVE+1
 . I I'="0",I'="" S INACTIVE=INACTIVE+1
 . S A=$P(Z,"^",5)
 . I A="P" S PUB=PUB+1
 . I A="S" S SUBS=SUBS+1
 . I A="A" S AGRE=AGRE+1
 . I A="R" S RESTR=RESTR+1
 . I $P(Z,"^",3)="" S NOROU=NOROU+1
 W !,"File 8994 (REMOTE PROCEDURE) counts:"
 W !,"  total:          ",TOT
 W !,"  active:         ",ACTIVE
 W !,"  inactive*:      ",INACTIVE
 W !,"  public:         ",PUB
 W !,"  subscription:   ",SUBS
 W !,"  agreement:      ",AGRE
 W !,"  restricted:     ",RESTR
 W !,"  no routine set: ",NOROU,!
 Q
 ;
