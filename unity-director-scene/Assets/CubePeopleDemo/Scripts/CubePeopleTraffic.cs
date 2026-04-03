using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

namespace CubePeople
{
    public class CubePeopleTraffic : MonoBehaviour
    {
        NavMeshAgent agent;
        public Vector2 minmaxSpeed = new Vector2(0.5f, 1.5f);

        public int playerState = 0; //0=entry, 1=stay
        public bool refreshDestination = false;
        bool dice;

        public float pauseTime = 1;
        float timeCount;

        //Way point
        public int targetPoint;
        public GameObject destinationFolder;
        List<Transform> wayPoints = new List<Transform>();
        
        //anim
        Animator anim;

        void Start()
        {
            anim = GetComponent<Animator>();
            agent = GetComponent<NavMeshAgent>();
            timeCount = pauseTime;

            TrySnapAgentToNavMesh();

            if (destinationFolder != null)
            {
                int count = destinationFolder.transform.childCount;
                for (int i = 0; i < count; i++)
                {
                    wayPoints.Add(destinationFolder.transform.GetChild(i));
                }
            }
            else
            {
                print("DestinationFolder is empty, navmesh does not work. (Scene object " + transform.gameObject.name.ToString() + ").");
            }

            agent.speed = RandomSpeed();
            targetPoint = ChooseWaypointIndex(-1);
            refreshDestination = true;
        }


        void Update()
        {
            if (wayPoints.Count == 0)
            {
                return;
            }
            else
            {
                float dist = Vector3.Distance(wayPoints[targetPoint].position, transform.position);
                if (dist < 0.35f)
                {
                    //arrived
                    if (!dice)
                    {
                        playerState = Random.Range(0, 2);
                        dice = true;
                    }

                    if (playerState == 1)
                    {
                        timeCount -= Time.deltaTime;    //wait
                        if (timeCount < 0)
                        {
                            timeCount = pauseTime;
                            dice = false;
                            playerState = 0;    //return zero
                        }
                    }
                    else
                    {
                        if (dice) dice = false;
                        targetPoint = ChooseWaypointIndex(targetPoint);    //new point
                        refreshDestination = true;
                    }
                }

                if (refreshDestination)
                {
                    if (agent != null && agent.isOnNavMesh)
                        agent.SetDestination(wayPoints[targetPoint].position);
                    refreshDestination = false;
                }

                if (!HasUsableNavMeshPath())
                    MoveTowardsWaypoint(wayPoints[targetPoint].position);
            }
            anim.SetFloat("Walk", agent.velocity.magnitude);
        }

        void TrySnapAgentToNavMesh()
        {
            if (agent == null || agent.isOnNavMesh)
                return;

            if (NavMesh.SamplePosition(transform.position, out var hit, 2f, NavMesh.AllAreas))
                agent.Warp(hit.position);
        }

        bool HasUsableNavMeshPath()
        {
            if (agent == null || !agent.isOnNavMesh)
                return false;

            if (agent.pathPending)
                return true;

            if (!agent.hasPath)
                return false;

            return agent.pathStatus != NavMeshPathStatus.PathInvalid;
        }

        void MoveTowardsWaypoint(Vector3 targetPosition)
        {
            Vector3 current = transform.position;
            float moveSpeed = agent != null ? agent.speed : (minmaxSpeed.x + minmaxSpeed.y) * 0.5f;
            Vector3 next = Vector3.MoveTowards(current, targetPosition, moveSpeed * Time.deltaTime);
            Vector3 direction = next - current;
            transform.position = next;

            if (direction.sqrMagnitude > 0.0001f)
                transform.rotation = Quaternion.Slerp(
                    transform.rotation,
                    Quaternion.LookRotation(direction.normalized, Vector3.up),
                    10f * Time.deltaTime);
        }

        public int RandomPoint()
        {
            int rPoint = -1;
            if (wayPoints.Count > 0)
            {
                rPoint = Random.Range(0, wayPoints.Count);
                
            }
            return rPoint;
        }

        int ChooseWaypointIndex(int excludeIndex)
        {
            if (wayPoints.Count == 0)
                return -1;

            var candidates = new List<int>();
            for (int i = 0; i < wayPoints.Count; i++)
            {
                if (i == excludeIndex)
                    continue;

                float distance = Vector3.Distance(transform.position, wayPoints[i].position);
                if (distance > 0.75f)
                    candidates.Add(i);
            }

            if (candidates.Count == 0)
                return RandomPoint();

            return candidates[Random.Range(0, candidates.Count)];
        }

        public float RandomSpeed()
        {
            return Random.Range(minmaxSpeed.x, minmaxSpeed.y);
        }
    }
}
