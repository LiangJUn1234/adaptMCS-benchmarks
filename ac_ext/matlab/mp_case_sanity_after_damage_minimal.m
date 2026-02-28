function out = mp_case_sanity_after_damage_minimal(case_data, state_payload)
%MP_CASE_SANITY_AFTER_DAMAGE_MINIMAL Apply damage and return minimal sanity metrics.

mpc_damaged = mp_apply_damage_state_minimal(case_data, state_payload);
out = mp_case_sanity_minimal(mpc_damaged);
end
