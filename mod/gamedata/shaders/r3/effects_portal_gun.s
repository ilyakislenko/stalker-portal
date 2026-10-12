-- portal-mod: a Portal 2 portal. Drawn by the R4 forward pass (r4_R_render.cpp render_forward, xr_3da portal_mod_draw)
-- as a 6-vertex quad; portal_gun.ps cuts the oval, draws the rim from Portal 2's colour ramps and noise.
-- Textures come from the user's Portal 2 install (tools/p2_assets.py), never shipped.

function normal(shader, t_base, t_second, t_detail)
    shader:begin("portal_gun", "portal_gun")
        :sorting(2, false)
        :blend(true, blend.srcalpha, blend.invsrcalpha)
        :zb(true, false)
        :fog(false)
    shader:dx10cullmode(1)

    shader:dx10texture("s_noise", "portal_mod\\portal_noise")
    shader:dx10texture("s_ramp_blue", "portal_mod\\portal_ramp_blue")
    shader:dx10texture("s_ramp_orange", "portal_mod\\portal_ramp_orange")
    shader:dx10texture("s_view", "$user$portal0") -- the view through the portal (engine portal pass, HDR)

    shader:dx10sampler("smp_linear")
    shader:dx10sampler("smp_rtlinear")
end
