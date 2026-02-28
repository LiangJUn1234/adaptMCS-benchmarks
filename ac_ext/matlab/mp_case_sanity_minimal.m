function out = mp_case_sanity_minimal(case_data)
%MP_CASE_SANITY_MINIMAL Return minimal case sanity counts/totals.
%   out = MP_CASE_SANITY_MINIMAL(case_data) accepts MATPOWER case name or
%   case struct and returns scalar counts for quick before/after checks.

mpc = local_load_case(case_data);

[F_BUS, T_BUS, BR_R, BR_X, BR_B, RATE_A, RATE_B, RATE_C, TAP, SHIFT, ...
    BR_STATUS, PF, QF, PT, QT, MU_SF, MU_ST, ANGMIN, ANGMAX, ...
    MU_ANGMIN, MU_ANGMAX] = idx_brch(); %#ok<ASGLU>
[GEN_BUS, PG, QG, QMAX, QMIN, VG, MBASE, GEN_STATUS, PMAX, PMIN, ...
    MU_PMAX, MU_PMIN, MU_QMAX, MU_QMIN, PC1, PC2, QC1MIN, QC1MAX, ...
    QC2MIN, QC2MAX, RAMP_AGC, RAMP_10, RAMP_30, RAMP_Q, APF] = idx_gen(); %#ok<ASGLU>
[BUS_I, BUS_TYPE, PD, QD, GS, BS, BUS_AREA, VM, VA, BASE_KV, ZONE, ...
    VMAX, VMIN] = idx_bus(); %#ok<ASGLU>

out = struct();
out.n_bus = size(mpc.bus, 1);
out.n_branch = size(mpc.branch, 1);
out.n_gen = size(mpc.gen, 1);
out.n_branch_online = sum(mpc.branch(:, BR_STATUS) == 1);
out.pmax_online_total = sum(mpc.gen(mpc.gen(:, GEN_STATUS) == 1, PMAX));
out.pd_total = sum(mpc.bus(:, PD));
end

function mpc = local_load_case(case_data)
if ischar(case_data) || isstring(case_data)
    mpc = loadcase(char(case_data));
elseif isstruct(case_data)
    mpc = case_data;
else
    error('case_data must be MATPOWER case name or struct.');
end
end
