function mpc_out = mp_apply_damage_state_minimal(case_data, state_payload)
%MP_APPLY_DAMAGE_STATE_MINIMAL Apply discrete damage state to a MATPOWER case.
%   mpc_out = MP_APPLY_DAMAGE_STATE_MINIMAL(case_data, state_payload)
%   accepts MATPOWER case name or struct and JSON/struct damage state.
%
%   Conservative bus outage rule:
%   - set BUS_TYPE=4 (isolated),
%   - set all incident branches BR_STATUS=0,
%   - set generators on that bus GEN_STATUS=0 and PMAX=0.

mpc_out = local_load_case(case_data);
state = local_parse_state(state_payload);

[F_BUS, T_BUS, BR_R, BR_X, BR_B, RATE_A, RATE_B, RATE_C, TAP, SHIFT, ...
    BR_STATUS, PF, QF, PT, QT, MU_SF, MU_ST, ANGMIN, ANGMAX, ...
    MU_ANGMIN, MU_ANGMAX] = idx_brch(); %#ok<ASGLU>
[GEN_BUS, PG, QG, QMAX, QMIN, VG, MBASE, GEN_STATUS, PMAX, PMIN, ...
    MU_PMAX, MU_PMIN, MU_QMAX, MU_QMIN, PC1, PC2, QC1MIN, QC1MAX, ...
    QC2MIN, QC2MAX, RAMP_AGC, RAMP_10, RAMP_30, RAMP_Q, APF] = idx_gen(); %#ok<ASGLU>
[BUS_I, BUS_TYPE, PD, QD, GS, BS, BUS_AREA, VM, VA, BASE_KV, ZONE, ...
    VMAX, VMIN] = idx_bus(); %#ok<ASGLU>

n_branch = size(mpc_out.branch, 1);
n_bus = size(mpc_out.bus, 1);
n_gen = size(mpc_out.gen, 1);

line_out = local_get_field_vector(state, 'line_out', n_branch);
bus_out = local_get_field_vector(state, 'bus_out', n_bus);
gen_scale = local_get_field_vector(state, 'gen_scale', n_gen);

% 1) Apply direct line outages.
mpc_out.branch(line_out > 0.5, BR_STATUS) = 0;

% 2) Apply generator derating. Scale PMAX and set offline if scale <= 0.
for gi = 1:n_gen
    scale = gen_scale(gi);
    if ~isfinite(scale)
        error('gen_scale contains non-finite value at index %d', gi);
    end
    if scale <= 0
        mpc_out.gen(gi, GEN_STATUS) = 0;
        mpc_out.gen(gi, PMAX) = 0;
    else
        mpc_out.gen(gi, PMAX) = max(0, mpc_out.gen(gi, PMAX) * scale);
    end
end

% 3) Apply conservative bus outages.
outaged_bus_nums = mpc_out.bus(bus_out > 0.5, BUS_I);
for bi = 1:numel(outaged_bus_nums)
    bus_num = outaged_bus_nums(bi);

    bus_row = find(mpc_out.bus(:, BUS_I) == bus_num, 1, 'first');
    if ~isempty(bus_row)
        mpc_out.bus(bus_row, BUS_TYPE) = 4; % isolated
    end

    incident = (mpc_out.branch(:, F_BUS) == bus_num) | (mpc_out.branch(:, T_BUS) == bus_num);
    mpc_out.branch(incident, BR_STATUS) = 0;

    gen_on_bus = (mpc_out.gen(:, GEN_BUS) == bus_num);
    mpc_out.gen(gen_on_bus, GEN_STATUS) = 0;
    mpc_out.gen(gen_on_bus, PMAX) = 0;
end
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

function state = local_parse_state(payload)
if ischar(payload) || isstring(payload)
    state = jsondecode(char(payload));
elseif isstruct(payload)
    state = payload;
else
    error('state_payload must be JSON text or struct.');
end
end

function vec = local_get_field_vector(state, field_name, expected_len)
if ~isfield(state, field_name)
    error('Damage state missing field: %s', field_name);
end
vec = state.(field_name);
vec = vec(:);
if numel(vec) ~= expected_len
    error('Damage state field %s length mismatch (expected %d, got %d).', ...
        field_name, expected_len, numel(vec));
end
vec = double(vec);
end
