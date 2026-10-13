// portal-mod: quad from SV_VertexID (like water_puddles.vs). m_W = portal xform from level.portal_set:
// i = right * half width, j = up * half height, k = normal, c = centre.
// Vertices 0..5: the portal on the surface. 6..11 (E10): the same oval 1.5x larger, 0.5 m behind the surface. The
// wall hides it, except when the camera is closer than the near plane and the front quad and the wall are clipped:
// then it keeps the view through the portal on screen.
#include "common.h"

struct v2p_portal
{
    float2 uv : TEXCOORD0; // -1..1 across the portal
    float3 wpos : TEXCOORD1;
    float4 hpos : SV_POSITION;
};

static const float2 portal_quad[6] = {float2(-1.0, -1.0), float2(-1.0, 1.0), float2(1.0, -1.0), float2(-1.0, 1.0), float2(1.0, 1.0), float2(1.0, -1.0)};

v2p_portal main(uint vert_id : SV_VertexID)
{
    v2p_portal O;

    float2 q = portal_quad[vert_id % 6];
    float back = vert_id >= 6 ? 1.0 : 0.0;
    float2 p = q * (1.0 + 0.5 * back);
    O.wpos = mul(m_W, float4(p.x, p.y, -0.5 * back, 1.0));
    O.hpos = mul(m_VP, float4(O.wpos, 1.0));
    O.hpos.xy = get_taa_jitter(O.hpos);
    O.uv = q;

    return O;
}
