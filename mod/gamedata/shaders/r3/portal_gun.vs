// portal-mod: quad from SV_VertexID (like water_puddles.vs). m_W = portal xform from level.portal_set:
// i = right * half width, j = up * half height, k = normal, c = centre.
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

    float2 q = portal_quad[vert_id];
    O.wpos = mul(m_W, float4(q.x, q.y, 0.0, 1.0));
    O.hpos = mul(m_VP, float4(O.wpos, 1.0));
    O.hpos.xy = get_taa_jitter(O.hpos);
    O.uv = q;

    return O;
}
