/*
 * Minimal nonce scanner for a prepared 80-byte Bitcoin header.
 * Usage:
 *   native/mine_sha256d HEADER_HEX START_NONCE COUNT
 *
 * It does not construct blocks, talk to nodes, or change nTime.
 * OpenSSL supplies SHA-256. Intended only as a transparent reference scanner.
 */
#include <openssl/sha.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int hexval(char c){ if(c>='0'&&c<='9')return c-'0'; if(c>='a'&&c<='f')return c-'a'+10; if(c>='A'&&c<='F')return c-'A'+10; return -1; }
static int unhex(const char *s,unsigned char *o,size_t n){ for(size_t i=0;i<n;i++){int a=hexval(s[2*i]),b=hexval(s[2*i+1]);if(a<0||b<0)return 0;o[i]=(a<<4)|b;}return s[2*n]=='\0';}
static uint32_t le32(const unsigned char*p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static void setle32(unsigned char*p,uint32_t x){p[0]=x;p[1]=x>>8;p[2]=x>>16;p[3]=x>>24;}

static void sha256d(const unsigned char *m,size_t n,unsigned char out[32]){
    unsigned char a[32]; SHA256(m,n,a); SHA256(a,32,out);
}
/* Compact target, enough for positive Bitcoin-style v0.1 targets used here.
   Compare digest as a 256-bit little-endian integer with target. */
static void target_from_bits(uint32_t bits,unsigned char target_le[32]){
    memset(target_le,0,32);
    uint32_t mant=bits&0x007fffff; int exp=(bits>>24);
    int shift=exp-3;
    if(shift<0||shift>29){fprintf(stderr,"unsupported bits\n");exit(2);}
    target_le[shift]=(unsigned char)mant;
    target_le[shift+1]=(unsigned char)(mant>>8);
    target_le[shift+2]=(unsigned char)(mant>>16);
}
static int leq_le256(const unsigned char a[32],const unsigned char b[32]){
    for(int i=31;i>=0;i--){if(a[i]<b[i])return 1;if(a[i]>b[i])return 0;}return 1;
}
int main(int argc,char**argv){
    if(argc!=4){fprintf(stderr,"usage: %s HEADER_HEX START_NONCE COUNT\n",argv[0]);return 2;}
    if(strlen(argv[1])!=160){fprintf(stderr,"header must be 80 bytes hex\n");return 2;}
    unsigned char h[80],d[32],target[32];
    if(!unhex(argv[1],h,80)){fprintf(stderr,"bad hex\n");return 2;}
    uint64_t start=strtoull(argv[2],0,0),count=strtoull(argv[3],0,0);
    uint32_t bits=le32(h+72); target_from_bits(bits,target);
    for(uint64_t k=0;k<count && start+k<=0xffffffffULL;k++){
        uint32_t n=(uint32_t)(start+k); setle32(h+76,n); sha256d(h,80,d);
        if(leq_le256(d,target)){
            printf("FOUND nonce=%u hash=",n);
            for(int i=31;i>=0;i--)printf("%02x",d[i]);
            printf("\nheader=");
            for(int i=0;i<80;i++)printf("%02x",h[i]);
            printf("\n"); return 0;
        }
    }
    printf("NOT_FOUND start=%llu count=%llu\n",(unsigned long long)start,(unsigned long long)count);
    return 1;
}
