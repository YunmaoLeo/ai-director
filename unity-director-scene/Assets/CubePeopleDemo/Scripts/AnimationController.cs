using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using DirectorRuntime;

namespace CubePeople
{
    public class AnimationController : MonoBehaviour
    {

        Animator anim;
        public bool run;
        ReplayableActor replayableActor;
        Vector3 lastPosition;
        const float ReplayRunThreshold = 0.05f;

        void Start()
        {
            anim = GetComponent<Animator>();
            replayableActor = GetComponent<ReplayableActor>();
            lastPosition = transform.position;
            if (run) run = false;
        }


        void Update()
        {
            if (replayableActor != null && replayableActor.IsReplaying)
            {
                Vector3 replayVelocity = replayableActor.CurrentReplayVelocity;
                if (replayVelocity.sqrMagnitude <= 0.0001f)
                {
                    replayVelocity = (transform.position - lastPosition) / Mathf.Max(Time.deltaTime, 0.0001f);
                }

                run = replayVelocity.magnitude > ReplayRunThreshold;
            }
            else
            {
                if (Input.GetAxisRaw("Vertical") == 0 && Input.GetAxisRaw("Horizontal") == 0)
                {
                    run = false;
                }
                else
                {
                    run = true;
                }
            }

            anim.SetBool("Run", run);
            lastPosition = transform.position;
        }
    }
}
