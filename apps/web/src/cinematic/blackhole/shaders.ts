// GLSL ES 3.00 sources for the black hole. Units: Schwarzschild radius rs = 1.
// Screen space: "height units" — origin at viewport centre, y up, viewport height = 1.

export const FULLSCREEN_VS = /* glsl */ `#version 300 es
const vec2 P[3] = vec2[3](vec2(-1.,-1.), vec2(3.,-1.), vec2(-1.,3.));
out vec2 vUv;
void main(){ vec2 p = P[gl_VertexID]; vUv = p*.5+.5; gl_Position = vec4(p,0.,1.); }`;

const NOISE = /* glsl */ `
float hash13(vec3 p){ p = fract(p*.1031); p += dot(p, p.zyx+31.32); return fract((p.x+p.y)*p.z); }
float hash12(vec2 p){ vec3 q = fract(vec3(p.xyx)*.1031); q += dot(q, q.yzx+33.33); return fract((q.x+q.y)*q.z); }
float vnoise(vec3 x){
  vec3 i = floor(x), f = fract(x); f = f*f*(3.-2.*f);
  return mix(mix(mix(hash13(i), hash13(i+vec3(1,0,0)), f.x), mix(hash13(i+vec3(0,1,0)), hash13(i+vec3(1,1,0)), f.x), f.y),
             mix(mix(hash13(i+vec3(0,0,1)), hash13(i+vec3(1,0,1)), f.x), mix(hash13(i+vec3(0,1,1)), hash13(i+vec3(1,1,1)), f.x), f.y), f.z);
}
float fbm(vec3 p){ float a = .5, s = 0.; for(int i=0;i<4;i++){ s += a*vnoise(p); p = p*2.03 + vec3(1.7,9.2,3.1); a *= .5; } return s; }
`;

export const SCENE_FS = /* glsl */ `#version 300 es
precision highp float;
in vec2 vUv;
out vec4 o;
uniform vec2 uRes;
uniform float uTime, uIgnite, uIntensity;
uniform vec2 uMouse;
uniform vec2 uHole;      // current hole centre (height units)
uniform float uRadius;   // current shadow radius on screen (height units)
uniform float uK;        // ray spread per height unit
uniform float uCamDist, uTilt, uRoll, uRin, uRout, uDoppler;
uniform int uSteps;
uniform float uStarScale, uHdr, uPoint;
uniform vec2 uPointPos;
uniform vec2 uBody; uniform float uBodyR;
uniform float uFade;       // distance beyond the ring over which disk light fades out (height units)
const float BC = 2.598076; // critical impact parameter 3*sqrt(3)/2 rs
${NOISE}

vec3 ramp(float t){
  const vec3 BROWN = vec3(.038,.0066,.0006), AMBER = vec3(1.,.465,.101), WHITE = vec3(1.,.88,.68);
  t = clamp(t, 0., 1.6);
  vec3 c = mix(BROWN, AMBER, smoothstep(0., .55, t));
  c = mix(c, WHITE, smoothstep(.5, 1.05, t));
  return mix(c, vec3(1.,.97,.94), smoothstep(1.05, 1.6, t));
}

vec4 disk(vec3 pc, vec3 vd, float rc, float rOut){
  float phi = atan(pc.z, pc.x);
  float om = sqrt(.5/(rc*rc*rc));
  float ang = phi - om*uTime*2.4;               // differential rotation, inner faster
  float lr = log(rc);
  float n = fbm(vec3(lr*13., cos(ang)*1.9, sin(ang)*1.9));             // fine azimuthal streaks
  float sa = ang + lr*2.3;                                             // spiral dust lanes
  float lanes = fbm(vec3(lr*3.1, cos(sa)*2.6, sin(sa)*2.6) + 4.2);
  float x = uRin/rc;
  float T = pow(x, .75)*pow(max(1.-sqrt(x), 0.), .25)/.488;            // Shakura-Sunyaev profile, peak = 1
  float beta = min(sqrt(.5/max(rc-1., .2)), .72)*uDoppler;
  vec3 vel = beta*normalize(vec3(-pc.z, 0., pc.x));
  float gam = inversesqrt(1.-beta*beta);
  float g = sqrt(max(1.-1./rc, .02))/(gam*(1.+dot(vel, vd)));         // Doppler + gravitational shift
  float dens = smoothstep(uRin, uRin+.45, rc)*(1.-smoothstep(rOut*.55, rOut, rc));
  dens *= (.3 + 1.05*n)*(.5 + .62*lanes);
  float alpha = clamp(dens*(1.25 - .75*smoothstep(uRin, uRout, rc)), 0., .97);
  vec3 c = ramp(T*g*1.05)*(pow(T, 2.1)*pow(g, 3.)*1.25 + .02);
  c = mix(c, vec3(.88,.94,1.05)*dot(c, vec3(.33)), smoothstep(1.12, 1.7, g)*.4);
  return vec4(c, alpha);
}

vec3 stars(vec3 d){
  vec3 col = vec3(0.);
  for(int l=0; l<2; l++){
    float sc = uStarScale*(l==0 ? 1. : 2.3);
    vec3 p = d*sc, c = floor(p), f = fract(p);
    float h = hash13(c + float(l)*17.);
    if(h > (l==0 ? .975 : .99)){
      vec3 off = vec3(hash13(c+1.7), hash13(c+5.3), hash13(c+9.1))*.6+.2;
      float b = pow(hash13(c+3.1), 3.)*(l==0 ? 1.2 : .5);
      float tw = .75 + .25*sin(uTime*(1.+3.*h) + h*40.);
      vec3 tint = mix(vec3(1.,.82,.62), vec3(.8,.88,1.), hash13(c+7.7));
      col += tint*b*tw*smoothstep(.16, 0., length(f-off));
    }
  }
  return col;
}

void main(){
  vec2 uv = (gl_FragCoord.xy - .5*uRes)/uRes.y;
  vec2 s0 = uv - uHole;
  float cr = cos(uRoll), sr = sin(uRoll);
  vec2 s = vec2(cr*s0.x - sr*s0.y, sr*s0.x + cr*s0.y);
  float ringT = smoothstep(0., .45, uIgnite);
  float diskT = smoothstep(.15, .8, uIgnite);
  float dustT = smoothstep(.45, 1., uIgnite);
  float rOut = mix(uRin+.2, uRout, diskT);       // disk ignites inner -> outer

  float e = uTilt + uMouse.y*.026;
  float az = uMouse.x*.035 + sin(uTime*.05)*.012;
  vec3 cam = uCamDist*vec3(sin(az)*cos(e), sin(e), cos(az)*cos(e));
  vec3 f = -normalize(cam), rt = normalize(cross(f, vec3(0.,1.,0.))), up = cross(rt, f);
  vec3 d = normalize(f + (s.x*rt + s.y*up)*uK);

  vec3 p = cam, v = d;
  vec3 hv = cross(p, v);
  float h2 = dot(hv, hv), b = sqrt(h2);
  vec3 col = vec3(0.); float a = 0.;
  bool captured = b < BC;

  if(b > 18.){
    // Weak field: straight ray plus small deflection toward the hole.
    if(d.y*cam.y < 0.){
      float t = -cam.y/d.y; vec3 pc = cam + d*t; float rc = length(pc.xz);
      if(rc > uRin && rc < rOut){ vec4 dc = disk(pc, d, rc, rOut); col += dc.rgb*dc.a; a = dc.a; }
    }
    v = normalize(d - normalize(cam - d*dot(cam, d))*(2./b));
  } else if(diskT > 0. || ringT > 0.){
    for(int i=0; i<128; i++){
      if(i >= uSteps) break;
      float r = length(p);
      float dt = r*mix(.05, .18, smoothstep(2.5, 14., r));
      vec3 acc = -1.5*h2*p/(r*r*r*r*r);
      vec3 pp = p;
      v += acc*dt; p += v*dt;
      if(pp.y*p.y < 0.){
        float t = pp.y/(pp.y - p.y); vec3 pc = mix(pp, p, t); float rc = length(pc.xz);
        if(rc > uRin && rc < rOut){
          vec4 dc = disk(pc, normalize(v), rc, rOut);
          col += (1.-a)*dc.rgb*dc.a; a += (1.-a)*dc.a;
          if(a > .985) break;
        }
      }
      float rn = length(p);
      if(rn < 1.){ captured = true; break; }
      if(rn > uCamDist*1.25 && dot(p, v) > 0.) break;
    }
  }
  // Art-directed grade: disk light fades to black toward the headline; stars and dust are unaffected.
  float sl = length(s);
  float fadeW = uFade;
  float textFade = 1. - smoothstep(uRadius*1.01, uRadius + fadeW, sl);
  textFade *= textFade;
  col *= diskT*textFade;
  a *= diskT*mix(.35, 1., textFade);
  if(!captured) col += (1.-a)*stars(normalize(v))*dustT*.9;

  // Photon ring: the sharpest, brightest feature, exactly on the shadow edge.
  float px = (2.598/max(uRadius, 1e-3))/uRes.y;  // one scene pixel in impact-parameter units
  float dB = b - BC;
  float side = clamp(s.x/max(uRadius, 1e-3), -1., 1.);
  float asym = 1. + .55*side;                    // approaching side brighter
  float core = exp(-pow((dB - 1.2*px)/(1.6*px), 2.));
  float halo = dB > 0. ? exp(-dB/(16.*px))*.32 + exp(-dB/(90.*px))*.07 : exp(dB/(2.*px))*.25;
  vec3 ringCol = mix(vec3(1.,.66,.32), vec3(1.,.95,.86), core);
  col += (1.-a*.8)*ringCol*(core*3.2 + halo*1.4)*asym*ringT;

  // Glimmering dust haze in the disk plane, faintly lit by the disk.
  vec2 hq = s/max(uRadius, 1e-3);
  float rho = length(vec2(hq.x, hq.y*1.15));
  if(rho > .9 && dustT > 0.){
    float hang = atan(hq.y, hq.x) + uTime*.035/pow(rho, 1.5);
    float hn = fbm(vec3(cos(hang)*2.2, sin(hang)*2.2, log(rho)*9. - uTime*.02));
    float hz = hn*hn*exp(-(rho-1.)*mix(5., 2.2, smoothstep(.6, 2.2, 1./uRadius)))*smoothstep(.9, 1.02, rho);
    col += vec3(.95,.5,.2)*hz*.2*(1. + .5*side)*dustT*(1. - smoothstep(uRadius + fadeW*.6, uRadius + fadeW*1.8, sl));
  }

  // Tiny distant body for scale, lit from the hole.
  vec2 bd = uv - uBody; float bl = length(bd);
  if(bl < uBodyR*1.2){
    float m = smoothstep(uBodyR, uBodyR*.85, bl);
    col *= 1. - m*dustT;
    vec2 lightDir = normalize(uHole - uBody);
    float rim = smoothstep(uBodyR*.55, uBodyR, bl)*m*pow(max(dot(normalize(bd), lightDir), 0.), 3.);
    col += vec3(1.,.78,.5)*rim*1.6*dustT;
  }

  // The point of light handed over from the vault seam.
  float pd = length(uv - uPointPos);
  col += vec3(1.,.86,.64)*uPoint*(exp(-pd*140.)*6. + exp(-pd*22.)*.45);

  o = vec4(col*uHdr, 1.);
}`;

export const PARTICLE_VS = /* glsl */ `#version 300 es
precision highp float;
layout(location=0) in vec4 aOrbit;   // radius, eccentricity, phase, brightness
layout(location=1) in vec4 aMeta;    // inclination, node, size, seed
uniform vec3 uCam, uF, uRt, uUp;
uniform vec2 uHole, uRes;
uniform float uK, uRoll, uTime, uDust, uCamDist, uPx;
out float vB; out vec3 vC;
void main(){
  float r0 = aOrbit.x, ecc = aOrbit.y;
  float nu = aOrbit.z + uTime*sqrt(.5/(r0*r0*r0))*2.4;
  float r = r0*(1.-ecc*ecc)/(1.+ecc*cos(nu));
  vec3 pos = vec3(cos(nu)*r, 0., sin(nu)*r);
  float ci = cos(aMeta.x), si = sin(aMeta.x); pos = vec3(pos.x, pos.y*ci - pos.z*si, pos.y*si + pos.z*ci);
  float cn = cos(aMeta.y), sn = sin(aMeta.y); pos = vec3(pos.x*cn + pos.z*sn, pos.y, -pos.x*sn + pos.z*cn);
  vec3 rel = pos - uCam;
  float z = dot(rel, uF);
  if(z < .5){ gl_Position = vec4(2.,2.,2.,1.); gl_PointSize = 0.; vB = 0.; vC = vec3(0.); return; }
  vec2 th = vec2(dot(rel, uRt), dot(rel, uUp))/z;
  float ts = length(th) + 1e-6, vis = 1.;
  if(z > uCamDist){
    // Point-lens image of a particle behind the hole; hidden if it lands in the shadow.
    float tE2 = 2.*(z - uCamDist)/(uCamDist*z);
    float ti = .5*(ts + sqrt(ts*ts + 4.*tE2));
    th *= ti/ts; ts = ti;
    vis = smoothstep(2.598/uCamDist, 2.75/uCamDist, ts);
  }
  vec2 s = th/uK;
  float cr = cos(uRoll), sr = sin(uRoll);
  vec2 sc = vec2(cr*s.x + sr*s.y, -sr*s.x + cr*s.y);   // inverse of the scene's roll
  vec2 q = uHole + sc;
  gl_Position = vec4(q.x*2.*uRes.y/uRes.x, q.y*2., 0., 1.);
  float seed = aMeta.w;
  float tw = .45 + .55*pow(.5 + .5*sin(uTime*(1.3 + seed*3.7) + seed*61.), 6.);
  gl_PointSize = clamp(aMeta.z*(uCamDist/z)*uPx, 1., 6.);
  vB = vis*uDust*tw*aOrbit.w*(1.6/(1. + .12*r));
  vC = mix(vec3(1.,.6,.28), vec3(1.,.93,.84), seed);
}`;

export const PARTICLE_FS = /* glsl */ `#version 300 es
precision highp float;
in float vB; in vec3 vC;
uniform float uHdr;
out vec4 o;
void main(){ float d = length(gl_PointCoord - .5); o = vec4(vC*vB*smoothstep(.5, 0., d)*uHdr, 1.); }`;

export const DOWN_FS = /* glsl */ `#version 300 es
precision highp float;
in vec2 vUv; out vec4 o;
uniform sampler2D uTex; uniform vec2 uTexel; uniform float uThreshold; uniform int uPrefilter;
vec3 s(float x, float y){ return texture(uTex, vUv + vec2(x, y)*uTexel).rgb; }
void main(){
  vec3 c = s(0.,0.)*.125 + (s(-2.,2.)+s(2.,2.)+s(-2.,-2.)+s(2.,-2.))*.03125
         + (s(0.,2.)+s(-2.,0.)+s(2.,0.)+s(0.,-2.))*.0625 + (s(-1.,1.)+s(1.,1.)+s(-1.,-1.)+s(1.,-1.))*.125;
  if(uPrefilter == 1){
    float br = max(c.r, max(c.g, c.b)), knee = uThreshold*.5;
    float soft = clamp(br - uThreshold + knee, 0., 2.*knee); soft = soft*soft/(4.*knee + 1e-5);
    c *= max(soft, br - uThreshold)/max(br, 1e-5);
  }
  o = vec4(c, 1.);
}`;

export const UP_FS = /* glsl */ `#version 300 es
precision highp float;
in vec2 vUv; out vec4 o;
uniform sampler2D uTex; uniform vec2 uTexel;
vec3 s(float x, float y){ return texture(uTex, vUv + vec2(x, y)*uTexel).rgb; }
void main(){
  vec3 c = s(-1.,1.) + 2.*s(0.,1.) + s(1.,1.) + 2.*s(-1.,0.) + 4.*s(0.,0.) + 2.*s(1.,0.) + s(-1.,-1.) + 2.*s(0.,-1.) + s(1.,-1.);
  o = vec4(c/16., 1.);
}`;

export const COMPOSITE_FS = /* glsl */ `#version 300 es
precision highp float;
in vec2 vUv; out vec4 o;
uniform sampler2D uScene, uBloom;
uniform vec2 uRes, uHole;
uniform float uRadius, uBloomStr, uIntensity, uTime, uHdrInv;
float hash12(vec2 p){ vec3 q = fract(vec3(p.xyx)*.1031); q += dot(q, q.yzx+33.33); return fract((q.x+q.y)*q.z); }
vec3 aces(vec3 x){ return clamp((x*(2.51*x + .03))/(x*(2.43*x + .59) + .14), 0., 1.); }
void main(){
  float aspect = uRes.x/uRes.y;
  vec2 p = (vUv - .5)*vec2(aspect, 1.);
  vec2 dir = p - uHole; float dd = length(dir);
  float fr = exp(-pow((dd - uRadius)/(.03*uRadius + .006), 2.));
  vec2 off = dir/max(dd, 1e-4)*fr*.0022/vec2(aspect, 1.);      // chromatic fringe at the photon ring
  vec3 sc = vec3(texture(uScene, vUv + off).r, texture(uScene, vUv).g, texture(uScene, vUv - off).b);
  vec3 hdr = (sc + texture(uBloom, vUv).rgb*uBloomStr)*uHdrInv*uIntensity;
  vec3 m = pow(aces(hdr*1.05), vec3(1./2.2));
  float vig = smoothstep(1.35, .3, length((vUv - .5)*vec2(aspect*.8, 1.2)));
  m *= mix(.62, 1., vig);
  float lum = dot(m, vec3(.299,.587,.114));
  m += (hash12(gl_FragCoord.xy + fract(uTime*7.13)*517.) - .5)*(.006 + .07*lum);
  o = vec4(max(m, 0.), 1.);
}`;
