using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.IO;
using System.Globalization;
using LSL;
using UXF;
using UXF.UI;

public enum ExperimentEventType
{
    OncomingOnly,
    BrakingOnly,
    Combined
}

public class ExperimentManager : MonoBehaviour
{
    [Header("UXF Settings")]
    public Session session;
    public PopupController popupController; // Reference to UXF Popup
    public GameObject startupPanel; // <--- [Added] Direct reference to Startup Panel
    public string greenBeltCondition = "GreenBelt";
    public string noGreenBeltCondition = "NoGreenBelt";
    public GameObject greenBeltObject; // Reference to the Green Belt parent object

    [Header("Experiment Settings")]
    public float initialRestTime = 0f; // Modified: 0 to skip rest/practice
    public float minISI = 60f;
    public float maxISI = 100f;
    public float avgSpeedEstimate = 28f; // ~100 km/h
    public int eventsPerType = 15; // 15 * 3 = 45 total

    [Header("Experiment Skills")]
    public ExperimentSkill oncomingSkill;
    public ExperimentSkill brakingSkill;
    public ExperimentSkill combinedSkill;
    public StanfordScaleUI stanfordScale; // Reference to Stanford Scale UI

    [Header("Event Parameters")]
    public float brakingOnlyDecel = 7.0f; // m/s2 (Increased for urgency)
    public float combinedDecel = 7.0f; // m/s2 (Increased for urgency)
    public float combinedEventDelay = 0.3f; // 300ms delay between Oncoming and Braking
    public float busSpeed = 25f; // m/s
    public float oncomingSpawnDistance = 250f; // Distance ahead of player to spawn bus

    [Header("Traffic Flow")]
    public BackgroundTrafficSpawner trafficSpawner;
    public float trafficFlowRate = 3600f; // Vehicles/hour

    [Header("References")]
    public Transform playerCar;
    public LeadCarController leadCar;
    public OncomingTruckController oncomingTruck; // Added reference
    public GameObject busPrefab;
    public LSLMarkerStream lslStream;

    private List<ExperimentEventType> eventQueue;
    private bool isExperimentRunning = false;
    private string currentStatus = "Setup";
    private RoadUtils roadUtils;
    private string currentConditionPrefix = "";
    public string CurrentConditionPrefix => currentConditionPrefix;
    private TreadmillSystem treadmillSystem;
    private float distanceBaselineRaw = 0f;
    private bool e2eMode = false;
    private string e2eExperimentName = "";
    private string e2ePpid = "";
    private int e2eSessionNumber = 1;
    private string e2eUxfRoot = "";
    private float e2eDistanceScale = 1f;
    private int e2ePracticeDurationSeconds = -1;
    private int e2eMainBlockDurationSeconds = -1;
    private float e2eStanfordTimeoutSeconds = -1f;
    private float e2eEndDelaySeconds = -1f;
    private bool e2eQuitOnFinish = true;
    private bool e2eSessionEnded = false;

    [Header("Distance Based Logic")]
    [Tooltip("Total accumulated distance in meters")]
    public float totalDistanceTraveled = 0f;
    [Tooltip("Total driving duration in seconds (active time)")]
    public float totalDrivingDuration = 0f;

    // Cache the duration limit for the current trial to avoid UXF lookup errors in Update
    private float currentTrialDurationLimit = -1f;
    
    // Removed Loop Logic as it is handled by external InfiniteLoopSystem
    // public float loopDistance = 5000f; 
    // public Transform roadStartPoint;
    // public Transform roadEndPoint;

    private float lastFrameZ = 0f;
    private float zDistanceTraveled = 0f;
    private float speedDistanceTraveled = 0f;
    private Vector3 initialCarPosition;
    private Quaternion initialCarRotation;
    private List<float> eventDistanceSchedule = new List<float>();

    // [Added] Flag to track if Stanford Scale has been shown in Practice
    private bool isCurrentBlockPractice = false;
    private bool practiceScaleTriggered = false;
    private bool isPracticeEndSequenceStarted = false; // Added to prevent multiple triggers at end of practice
    private readonly List<float> practiceEventTimes = new List<float>();
    private int practiceNextEventIndex = 0;

    void Awake()
    {
        Application.runInBackground = true;
#if ENABLE_INPUT_SYSTEM
        UnityEngine.InputSystem.InputSystem.settings.backgroundBehavior =
            UnityEngine.InputSystem.InputSettings.BackgroundBehavior.IgnoreFocus;
#endif
    }

    void SetupExperimentEnvironment()
    {
        // 1. Fix Camera
        RCCP_Camera rccCamera = FindObjectOfType<RCCP_Camera>();
        if (rccCamera != null)
        {
            RCCP_CarController playerVehicle = null;
            
            // Priority 1: Use Inspector Assignment
            if (playerCar != null) 
            {
                playerVehicle = playerCar.GetComponent<RCCP_CarController>();
                Debug.Log($"[ExperimentManager] Searching Player... Inspector assigned: {(playerVehicle ? playerVehicle.name : "null")}");
            }
            
            // Priority 2: Use Tag "Player"
            if (playerVehicle == null)
            {
                 GameObject p = GameObject.FindGameObjectWithTag("Player");
                 if (p != null) playerVehicle = p.GetComponent<RCCP_CarController>();
                 Debug.Log($"[ExperimentManager] Searching Player... Tag 'Player': {(playerVehicle ? playerVehicle.name : "null")}");
            }

            // Priority 3: Find any controllable car (excluding LeadCar)
            if (playerVehicle == null)
            {
                RCCP_CarController[] cars = FindObjectsOfType<RCCP_CarController>();
                foreach (var car in cars)
                {
                    // Skip Lead Car if referenced
                    if (leadCar != null && car.gameObject == leadCar.gameObject) continue;
                    
                    // Skip if name contains "Lead" or "AI" just in case
                    if (car.name.Contains("Lead") || car.name.Contains("AI")) continue;

                    // Prefer cars that are controllable and NOT external control
                    if (car.canControl && !car.externalControl)
                    {
                        playerVehicle = car;
                        break;
                    }
                }
                Debug.Log($"[ExperimentManager] Searching Player... Auto-Scan: {(playerVehicle ? playerVehicle.name : "null")}");
            }

            if (playerVehicle != null)
            {
                // Register as global player
                RCCP.RegisterPlayerVehicle(playerVehicle);
                
                // Ensure camera is valid before proceeding
                if (rccCamera == null)
                {
                    Debug.LogError("[ExperimentManager] RCCP_Camera not found!");
                    return;
                }

                // 1. Force Set Target
                rccCamera.SetTarget(playerVehicle);
                
                // 2. Set Mode
                rccCamera.cameraMode = RCCP_Camera.CameraMode.FPS;
                
                // 3. Auto-fix hood camera position if missing or bad
                FixHoodCameraPosition(playerVehicle);

                // 4. Reset Camera (Important to apply changes)
                // Use Try-Catch to avoid crash if something internal in RCCP is null
                try 
                {
                    rccCamera.ResetCamera();
                }
                catch (System.Exception e)
                {
                    Debug.LogError($"[ExperimentManager] RCCP_Camera.ResetCamera failed: {e.Message}. Fallback to manual setup.");
                    // Fallback: manually set parent and reset transform if ResetCamera fails
                    if (playerVehicle.GetComponentInChildren<RCCP_HoodCamera>())
                    {
                        rccCamera.transform.SetParent(playerVehicle.GetComponentInChildren<RCCP_HoodCamera>().transform);
                        rccCamera.transform.localPosition = Vector3.zero;
                        rccCamera.transform.localRotation = Quaternion.identity;
                    }
                }
                
                // --- NEW FIX: Force Camera State AGAIN after a small delay ---
                // RCCP might override our settings in its own LateUpdate or Start.
                // We start a coroutine to enforce our settings one frame later.
                StartCoroutine(EnforceCameraState(rccCamera, playerVehicle));
                
                Debug.Log($"[ExperimentManager] SUCCESS: Camera linked to player '{playerVehicle.name}' (Mode: FPS).");
            }
            else
            {
                Debug.LogError("[ExperimentManager] FAILED: Could not find any valid Player Vehicle!");
            }
        }
    }

    IEnumerator EnforceCameraState(RCCP_Camera cam, RCCP_CarController target)
    {
        // Wait for 2 frames to let all other scripts (TrafficSpawner, RCCP internals) finish their Start/Update cycles
        yield return null; 
        yield return null;

        if (cam != null && target != null)
        {
            // Double check if target was stolen
            if (RCCP_SceneManager.Instance.activePlayerVehicle != target)
            {
                RCCP.RegisterPlayerVehicle(target);
            }
            
            cam.SetTarget(target);
            cam.cameraMode = RCCP_Camera.CameraMode.FPS;
            cam.ResetCamera();
            Debug.Log("[ExperimentManager] Enforced Camera State (Anti-Hijack Check Passed).");
        }
    }

    void FixHoodCameraPosition(RCCP_CarController playerVehicle)
    {
        if (playerVehicle == null) return;

        RCCP_HoodCamera hoodCam = playerVehicle.GetComponentInChildren<RCCP_HoodCamera>();
        
        // If no hood camera exists, create one
        if (hoodCam == null)
        {
            GameObject hoodCamObj = new GameObject("HoodCamera");
            hoodCamObj.transform.SetParent(playerVehicle.transform, false);
            hoodCam = hoodCamObj.AddComponent<RCCP_HoodCamera>();
        }

        // Calculate bounds to find a good spot
        Quaternion originalRot = playerVehicle.transform.rotation;
        playerVehicle.transform.rotation = Quaternion.identity;

        Bounds bounds = new Bounds();
        bool init = false;
        Renderer[] renderers = playerVehicle.GetComponentsInChildren<Renderer>();
        foreach (Renderer r in renderers)
        {
            if (r is TrailRenderer || r is ParticleSystemRenderer) continue;
            if (!init)
            {
                bounds = r.bounds;
                init = true;
            }
            else
            {
                bounds.Encapsulate(r.bounds);
            }
        }

        playerVehicle.transform.rotation = originalRot;

        if (init)
        {
            // Calculate relative position. 
            // Since we reset rotation to identity, bounds are world-aligned.
            // Vehicle pivot is at playerVehicle.transform.position.
            Vector3 vehiclePos = playerVehicle.transform.position;
            Vector3 max = bounds.max;
            Vector3 min = bounds.min;
            
            // Aim for a "Roof/Hood" view: High enough to see over, forward enough to feel like driving.
            // X = 0 (Center)
            // Y = Roof height (max.y) relative to pivot
            // Z = Front area. Let's say 80% towards the front from center.
            
            float height = max.y - vehiclePos.y;
            float length = max.z - min.z;
            float forwardOffset = (max.z - vehiclePos.z) - (length * 0.2f); // 20% back from the very front nose

            // Set local position
            // Assuming pivot is at (0,0,0) locally for X
            hoodCam.transform.localPosition = new Vector3(0f, height * 0.9f, forwardOffset);
            
            Debug.Log($"[ExperimentManager] Fixed Hood Camera Position: {hoodCam.transform.localPosition}");
        }
    }

    [System.Serializable]
    public struct ScheduledEvent
    {
        public float distance;
        public ExperimentEventType type;
        public string eventName; // Custom event name (e.g. "Oncoming_1", "Combined_3")
        public string remark; // For questionnaires/scales
    }

    private List<ScheduledEvent> fixedSchedule = new List<ScheduledEvent>();
    private readonly List<ScheduledEvent> mainSchedule = new List<ScheduledEvent>();
    private int mainNextEventIndex = 0;
    private int mainTriggeredEventCount = 0;
    private string mainScheduleCondition = "";
    private bool mainScheduleLoaded = false;
    private bool isSkippingBlock = false;

    string BuildMarkerName(string eventName)
    {
        if (string.IsNullOrEmpty(eventName)) return currentConditionPrefix;
        if (!string.IsNullOrEmpty(currentConditionPrefix) && eventName.StartsWith(currentConditionPrefix))
            return eventName;
        return $"{currentConditionPrefix}{eventName}";
    }

    string GetEventBaseName(string eventName)
    {
        if (string.IsNullOrEmpty(eventName)) return "";
        if (!string.IsNullOrEmpty(currentConditionPrefix) && eventName.StartsWith(currentConditionPrefix))
            return eventName.Substring(currentConditionPrefix.Length);
        return eventName;
    }

    void PrepareEvents(string condition, int phaseIndex)
    {
        // Load the fixed schedule based on condition and phase
        fixedSchedule.Clear();
        
        if (condition == "Practice")
        {
            // --- PRACTICE SCENARIO (8 Mins) ---
            for(int i=1; i<=12; i++)
            {
                float dist = 500f + ((i - 1) * 600f);
                AddEvent(dist, ExperimentEventType.BrakingOnly, $"Practice_Braking_{i}");
            }
            Debug.Log("[ExperimentManager] Loaded PRACTICE schedule.");
        }
        else if (condition == greenBeltCondition)
        {
            // --- CONDITION A (Green Belt) ---
            if (phaseIndex == 1)
            {
                // Phase 1 (0-20 min)
                AddEvent(2667f, ExperimentEventType.OncomingOnly, "Oncoming_1");
                AddEvent(5445f, ExperimentEventType.Combined, "Combined_1"); 
                AddEvent(8167f, ExperimentEventType.BrakingOnly, "Braking_1");
                AddEvent(10945f, ExperimentEventType.OncomingOnly, "Oncoming_2");
                AddEvent(13667f, ExperimentEventType.Combined, "Combined_2"); 
                AddEvent(16445f, ExperimentEventType.BrakingOnly, "Braking_2");
                AddEvent(19167f, ExperimentEventType.OncomingOnly, "Oncoming_3");
                AddEvent(21945f, ExperimentEventType.Combined, "Combined_3"); 
                AddEvent(24723f, ExperimentEventType.BrakingOnly, "Braking_3");
                AddEvent(27501f, ExperimentEventType.OncomingOnly, "Oncoming_4");
                AddEvent(30223f, ExperimentEventType.Combined, "Combined_4"); 
                AddEvent(33000f, ExperimentEventType.BrakingOnly, "Braking_4");
            }
            else if (phaseIndex == 2)
            {
                // Phase 2 (20-40 min)
                AddEvent(35723f, ExperimentEventType.OncomingOnly, "Oncoming_5");
                AddEvent(38501f, ExperimentEventType.BrakingOnly, "Braking_5");
                AddEvent(41223f, ExperimentEventType.Combined, "Combined_5"); 
                AddEvent(44001f, ExperimentEventType.OncomingOnly, "Oncoming_6");
                AddEvent(46723f, ExperimentEventType.BrakingOnly, "Braking_6");
                AddEvent(49501f, ExperimentEventType.Combined, "Combined_6"); 
                AddEvent(52223f, ExperimentEventType.OncomingOnly, "Oncoming_7");
                AddEvent(55001f, ExperimentEventType.BrakingOnly, "Braking_7");
                AddEvent(57723f, ExperimentEventType.Combined, "Combined_7"); 
                AddEvent(60501f, ExperimentEventType.OncomingOnly, "Oncoming_8");
                AddEvent(63223f, ExperimentEventType.BrakingOnly, "Braking_8");
                AddEvent(66000f, ExperimentEventType.Combined, "Combined_8");
            }
            else if (phaseIndex == 3)
            {
                // Phase 3 (40-60 min)
                AddEvent(68723f, ExperimentEventType.OncomingOnly, "Oncoming_9");
                AddEvent(71501f, ExperimentEventType.BrakingOnly, "Braking_9");
                AddEvent(74223f, ExperimentEventType.Combined, "Combined_9"); 
                AddEvent(77001f, ExperimentEventType.OncomingOnly, "Oncoming_10");
                AddEvent(79723f, ExperimentEventType.BrakingOnly, "Braking_10");
                AddEvent(82501f, ExperimentEventType.Combined, "Combined_10"); 
                AddEvent(85223f, ExperimentEventType.OncomingOnly, "Oncoming_11");
                AddEvent(88001f, ExperimentEventType.BrakingOnly, "Braking_11");
                AddEvent(90723f, ExperimentEventType.Combined, "Combined_11"); 
                AddEvent(93501f, ExperimentEventType.OncomingOnly, "Oncoming_12");
                AddEvent(96223f, ExperimentEventType.BrakingOnly, "Braking_12");
                AddEvent(99000f, ExperimentEventType.Combined, "Combined_12");
            }
            Debug.Log($"[ExperimentManager] Loaded Condition A (GreenBelt) schedule for Phase {phaseIndex}.");
        }
        else if (condition == noGreenBeltCondition)
        {
             // --- CONDITION B (No Green Belt) ---
             if (phaseIndex == 1)
             {
                 // Phase 1 (0-20 min)
                 AddEvent(2500f, ExperimentEventType.Combined, "Combined_1_B"); 
                 AddEvent(5200f, ExperimentEventType.BrakingOnly, "Braking_1_B");
                 AddEvent(7900f, ExperimentEventType.OncomingOnly, "Oncoming_1_B");
                 AddEvent(10600f, ExperimentEventType.Combined, "Combined_2_B"); 
                 AddEvent(13300f, ExperimentEventType.BrakingOnly, "Braking_2_B");
                 AddEvent(16000f, ExperimentEventType.OncomingOnly, "Oncoming_2_B");
                 AddEvent(18700f, ExperimentEventType.Combined, "Combined_3_B"); 
                 AddEvent(21400f, ExperimentEventType.BrakingOnly, "Braking_3_B");
                 AddEvent(24100f, ExperimentEventType.OncomingOnly, "Oncoming_3_B");
                 AddEvent(26800f, ExperimentEventType.Combined, "Combined_4_B"); 
                AddEvent(29500f, ExperimentEventType.BrakingOnly, "Braking_4_B");
                AddEvent(31700f, ExperimentEventType.OncomingOnly, "Oncoming_4_B");
             }
             else if (phaseIndex == 2)
             {
                 // Phase 2 (20-40 min)
                 AddEvent(35000f, ExperimentEventType.BrakingOnly, "Braking_5_B");
                 AddEvent(37800f, ExperimentEventType.OncomingOnly, "Oncoming_5_B");
                 AddEvent(40600f, ExperimentEventType.Combined, "Combined_5_B");
                 AddEvent(43400f, ExperimentEventType.BrakingOnly, "Braking_6_B");
                 AddEvent(46200f, ExperimentEventType.OncomingOnly, "Oncoming_6_B");
                 AddEvent(49000f, ExperimentEventType.Combined, "Combined_6_B");
                 AddEvent(51800f, ExperimentEventType.BrakingOnly, "Braking_7_B");
                 AddEvent(54600f, ExperimentEventType.OncomingOnly, "Oncoming_7_B");
                 AddEvent(57400f, ExperimentEventType.Combined, "Combined_7_B");
                 AddEvent(60200f, ExperimentEventType.BrakingOnly, "Braking_8_B");
                 AddEvent(63000f, ExperimentEventType.OncomingOnly, "Oncoming_8_B");
                 AddEvent(65800f, ExperimentEventType.Combined, "Combined_8_B");
             }
             else if (phaseIndex == 3)
             {
                 // Phase 3 (40-60 min)
                 AddEvent(68600f, ExperimentEventType.OncomingOnly, "Oncoming_9_B");
                 AddEvent(71400f, ExperimentEventType.Combined, "Combined_9_B");
                 AddEvent(74200f, ExperimentEventType.BrakingOnly, "Braking_9_B");
                 AddEvent(77000f, ExperimentEventType.OncomingOnly, "Oncoming_10_B");
                 AddEvent(79800f, ExperimentEventType.Combined, "Combined_10_B");
                 AddEvent(82600f, ExperimentEventType.BrakingOnly, "Braking_10_B");
                 AddEvent(85400f, ExperimentEventType.OncomingOnly, "Oncoming_11_B");
                 AddEvent(88200f, ExperimentEventType.Combined, "Combined_11_B");
                 AddEvent(91000f, ExperimentEventType.BrakingOnly, "Braking_11_B");
                 AddEvent(93800f, ExperimentEventType.OncomingOnly, "Oncoming_12_B");
                 AddEvent(96600f, ExperimentEventType.Combined, "Combined_12_B");
                 AddEvent(99400f, ExperimentEventType.BrakingOnly, "Braking_12_B");
             }
             Debug.Log($"[ExperimentManager] Loaded Condition B (NoGreenBelt) schedule for Phase {phaseIndex}.");
        }
        Debug.Log($"[ExperimentManager] Loaded {fixedSchedule.Count} fixed events from schedule.");
    }

    static string GetScheduleFilePath()
    {
        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", "Experiment_Event_Schedule.txt"));
    }

    static bool TryParseMainScheduleFromTxt(string fileContent, string condition, out List<ScheduledEvent> schedule)
    {
        schedule = new List<ScheduledEvent>();
        if (string.IsNullOrWhiteSpace(fileContent) || string.IsNullOrWhiteSpace(condition)) return false;

        static string NormalizeRemark(string remark)
        {
            if (string.IsNullOrWhiteSpace(remark)) return "";
            string trimmed = remark.Trim();
            int space = trimmed.IndexOf(' ');
            if (space >= 0) trimmed = trimmed.Substring(0, space);
            int paren = trimmed.IndexOf('(');
            if (paren >= 0) trimmed = trimmed.Substring(0, paren);
            return trimmed.Trim();
        }

        string sectionStart = condition == "GreenBelt" ? "2. 有隔离带环境" : (condition == "NoGreenBelt" ? "3. 无隔离带环境" : "");
        if (string.IsNullOrEmpty(sectionStart)) return false;

        bool inSection = false;
        var lines = fileContent.Split(new[] { "\r\n", "\n" }, System.StringSplitOptions.None);
        for (int i = 0; i < lines.Length; i++)
        {
            string line = lines[i];
            if (!inSection)
            {
                if (line.Contains(sectionStart))
                {
                    inSection = true;
                }
                continue;
            }

            if (condition == "GreenBelt" && line.Contains("3. 无隔离带环境")) break;

            if (!line.Contains("|")) continue;

            var parts = line.Split('|').Select(p => p.Trim()).ToArray();
            if (parts.Length < 4) continue;

            if (!int.TryParse(parts[0], out _)) continue;
            if (!float.TryParse(parts[1], out float distance)) continue;

            if (!System.Enum.TryParse(parts[2], out ExperimentEventType type)) continue;
            string eventName = parts[3];
            if (string.IsNullOrWhiteSpace(eventName)) continue;

            string remark = "";
            if (parts.Length >= 5) remark = NormalizeRemark(parts[4]);

            schedule.Add(new ScheduledEvent { distance = distance, type = type, eventName = eventName, remark = remark });
        }

        if (schedule.Count != 36) return false;
        schedule = schedule.OrderBy(e => e.distance).ToList();

        for (int i = 1; i < schedule.Count; i++)
        {
            if (schedule[i].distance <= schedule[i - 1].distance) return false;
        }

        return true;
    }

    List<ScheduledEvent> BuildFallbackMainSchedule(string condition)
    {
        var schedule = new List<ScheduledEvent>();

        if (condition == greenBeltCondition)
        {
            schedule.AddRange(BuildPhaseSchedule(greenBeltCondition, 1));
            schedule.AddRange(BuildPhaseSchedule(greenBeltCondition, 2));
            schedule.AddRange(BuildPhaseSchedule(greenBeltCondition, 3));
        }
        else if (condition == noGreenBeltCondition)
        {
            schedule.AddRange(BuildPhaseSchedule(noGreenBeltCondition, 1));
            schedule.AddRange(BuildPhaseSchedule(noGreenBeltCondition, 2));
            schedule.AddRange(BuildPhaseSchedule(noGreenBeltCondition, 3));
        }

        return schedule.OrderBy(e => e.distance).ToList();
    }

    List<ScheduledEvent> BuildPhaseSchedule(string condition, int phaseIndex)
    {
        var original = fixedSchedule;
        fixedSchedule = new List<ScheduledEvent>();
        PrepareEvents(condition, phaseIndex);
        var result = fixedSchedule.ToList();
        fixedSchedule = original;
        return result;
    }

    void ApplyDistanceScale(List<ScheduledEvent> schedule, float scale)
    {
        if (schedule == null) return;
        if (Mathf.Abs(scale - 1f) < 0.000001f) return;
        for (int i = 0; i < schedule.Count; i++)
        {
            var e = schedule[i];
            e.distance *= scale;
            schedule[i] = e;
        }
        schedule.Sort((a, b) => a.distance.CompareTo(b.distance));
    }

    void EnsureMainScheduleLoaded(string condition, bool resetProgress)
    {
        if (resetProgress || !mainScheduleLoaded || mainScheduleCondition != condition)
        {
            mainSchedule.Clear();
            mainNextEventIndex = 0;
            mainTriggeredEventCount = 0;
            mainScheduleCondition = condition;
            mainScheduleLoaded = false;

            try
            {
                string path = GetScheduleFilePath();
                if (File.Exists(path))
                {
                    string content = File.ReadAllText(path);
                    if (TryParseMainScheduleFromTxt(content, condition, out var parsed))
                    {
                        mainSchedule.AddRange(parsed);
                        mainScheduleLoaded = true;
                        Debug.Log($"[ExperimentManager] Loaded MAIN schedule from txt ({condition}): {mainSchedule.Count} events.");
                    }
                }
            }
            catch (System.Exception e)
            {
                Debug.LogWarning($"[ExperimentManager] Failed to load schedule txt. Fallback to built-in schedule. Error: {e.Message}");
            }

            if (!mainScheduleLoaded)
            {
                mainSchedule.AddRange(BuildFallbackMainSchedule(condition));
                mainScheduleLoaded = mainSchedule.Count == 36;
                Debug.Log($"[ExperimentManager] Loaded MAIN schedule from built-in fallback ({condition}): {mainSchedule.Count} events.");
            }

            if (e2eMode && mainSchedule.Count > 0 && Mathf.Abs(e2eDistanceScale - 1f) > 0.000001f)
            {
                ApplyDistanceScale(mainSchedule, e2eDistanceScale);
            }
        }
    }


    void AddEvent(float dist, ExperimentEventType type, string name, string remark = "")
    {
        fixedSchedule.Add(new ScheduledEvent { distance = dist, type = type, eventName = name, remark = remark });
    }

    static bool TryGetArg(string[] args, string key, out string value)
    {
        value = "";
        if (args == null) return false;
        for (int i = 0; i < args.Length; i++)
        {
            if (string.Equals(args[i], key, StringComparison.OrdinalIgnoreCase))
            {
                if (i + 1 < args.Length)
                {
                    value = args[i + 1];
                    return true;
                }
                return false;
            }
        }
        return false;
    }

    static bool HasArg(string[] args, string key)
    {
        if (args == null) return false;
        for (int i = 0; i < args.Length; i++)
        {
            if (string.Equals(args[i], key, StringComparison.OrdinalIgnoreCase)) return true;
        }
        return false;
    }

    void ConfigureE2EFromArgs()
    {
        string[] args = Environment.GetCommandLineArgs();
        e2eMode = HasArg(args, "--e2e");
        if (!e2eMode) return;

        if (TryGetArg(args, "--experiment", out var exp)) e2eExperimentName = exp;
        if (TryGetArg(args, "--ppid", out var ppid)) e2ePpid = ppid;
        if (TryGetArg(args, "--session", out var sessStr) && int.TryParse(sessStr, out var sn)) e2eSessionNumber = sn;
        if (TryGetArg(args, "--uxf_root", out var root)) e2eUxfRoot = root;

        if (TryGetArg(args, "--distance_scale", out var dsStr) && float.TryParse(dsStr, NumberStyles.Float, CultureInfo.InvariantCulture, out var ds))
            e2eDistanceScale = Mathf.Max(0.0001f, ds);

        if (TryGetArg(args, "--practice_sec", out var psStr) && int.TryParse(psStr, out var ps))
            e2ePracticeDurationSeconds = Mathf.Max(1, ps);

        if (TryGetArg(args, "--block_sec", out var bsStr) && int.TryParse(bsStr, out var bs))
            e2eMainBlockDurationSeconds = Mathf.Max(1, bs);

        if (TryGetArg(args, "--stanford_sec", out var ssStr) && float.TryParse(ssStr, NumberStyles.Float, CultureInfo.InvariantCulture, out var st))
            e2eStanfordTimeoutSeconds = Mathf.Max(0.01f, st);

        if (TryGetArg(args, "--end_delay_sec", out var edStr) && float.TryParse(edStr, NumberStyles.Float, CultureInfo.InvariantCulture, out var ed))
            e2eEndDelaySeconds = Mathf.Max(0f, ed);

        if (TryGetArg(args, "--quit_on_finish", out var qStr) && bool.TryParse(qStr, out var q))
            e2eQuitOnFinish = q;
    }

    void Start()
    {
        ConfigureE2EFromArgs();

        if (!e2eMode)
        {
            Time.timeScale = 0f;
            AudioListener.pause = true;
        }
        else
        {
            Time.timeScale = 1f;
            AudioListener.pause = false;
        }

        // [Fix] Auto-Bind Player Car if missing (Look for "M3_E46")
        if (playerCar == null)
        {
            GameObject pObj = GameObject.Find("M3_E46");
            if (pObj != null)
            {
                playerCar = pObj.transform;
                Debug.Log($"[ExperimentManager] Auto-bound Player Car to '{pObj.name}'");
            }
            else
            {
                Debug.LogError("[ExperimentManager] Player Car 'M3_E46' not found in scene!");
            }
        }

        // Initialize Default Skills if missing
        if (oncomingSkill == null) oncomingSkill = ScriptableObject.CreateInstance<Skill_OncomingVehicle>();
        if (brakingSkill == null)
        {
            var skill = ScriptableObject.CreateInstance<Skill_BrakingEvent>();
            skill.deceleration = brakingOnlyDecel;
            brakingSkill = skill;
        }
        if (combinedSkill == null)
        {
            var skill = ScriptableObject.CreateInstance<Skill_CombinedEvent>();
            skill.deceleration = combinedDecel;
            combinedSkill = skill;
        }

        SetupExperimentEnvironment();

        roadUtils = RoadUtils.Instance;
        if (roadUtils == null) roadUtils = FindObjectOfType<RoadUtils>();
        if (lslStream == null) lslStream = GetComponent<LSLMarkerStream>();
        if (session == null) session = GetComponent<Session>();
        treadmillSystem = FindObjectOfType<TreadmillSystem>();
        
        // --- UXF Popup Setup ---
        if (popupController == null)
        {
            popupController = FindObjectOfType<PopupController>();
            if (popupController == null) Debug.LogWarning("[ExperimentManager] PopupController not found in scene.");
        }

        // Subscribe to Block End for Transitions
        // MOVED: Logic moved down to ensure session is found first
        /*
        if (session != null)
        {
            session.onBlockEnd.AddListener(HandleBlockEnd);
        }
        */

        if (playerCar != null)
        {
            lastFrameZ = playerCar.transform.position.z;
            
            // [Added] Capture Initial Position for Reset
            initialCarPosition = playerCar.position;
            initialCarRotation = playerCar.rotation;
        }

        // Initialize Traffic
        if (trafficSpawner != null)
        {
            trafficSpawner.flowRate = trafficFlowRate;
            trafficSpawner.playerCar = playerCar;
        }

        if (session == null)
        {
            // Try to find Session globally if not assigned in Inspector
            session = FindObjectOfType<Session>();
        }

        // Subscribe to Block End for Transitions
        // Must do this AFTER finding the session!
        if (session != null)
        {
            // Remove previous listeners to avoid duplicates if re-enabled
            session.onBlockEnd.RemoveListener(HandleBlockEnd);
            session.onBlockEnd.AddListener(HandleBlockEnd);
            
            // [Fix] Auto-start Block 1 when Session begins (after Startup Panel)
            session.onSessionBegin.RemoveListener(OnSessionBegin);
            session.onSessionBegin.AddListener(OnSessionBegin);
        }

        // Subscribe to Lead Car physical events for precise marking
        if (leadCar != null)
        {
            leadCar.OnBrakeStart += (decel) => {
                SendMarker($"{currentConditionPrefix}LeadCar_Brake_Onset_Physical_{decel:F1}");
            };
            
            leadCar.OnBrakeEnd += () => {
                SendMarker($"{currentConditionPrefix}LeadCar_Brake_Release_Physical");
            };
        }
        
        PrepareEvents("Setup", 1); // Pre-load something safe? Or just empty.

        // --- FIX: Ensure GreenBelt is OFF by default on start ---
        // This prevents the user from seeing the GreenBelt before the first Practice trial begins
        if(greenBeltObject == null)
        {
            // Try to find by name if not assigned
            var obj = GameObject.Find("median"); // [Changed] User confirmed the name is "median"
            if (obj == null) obj = GameObject.Find("GreenBeltParent");
            if (obj == null) obj = GameObject.Find("GreenBelt");
            if (obj == null) obj = GameObject.Find("Vegetation");
            if (obj != null) greenBeltObject = obj;
        }

        if(greenBeltObject != null) 
        {
            greenBeltObject.SetActive(false);
            Debug.Log("[ExperimentManager] Default State: GreenBelt OFF (Waiting for Trial Start)");
        }
        else
        {
            Debug.LogWarning("[ExperimentManager] GreenBelt Object NOT FOUND! Please assign it in the Inspector or name it 'median'.");
        }

        if (session == null)
        {
            // Try to find Session globally if not assigned in Inspector
            session = FindObjectOfType<Session>();
        }

        // Auto-start experiment logic if we are not using UXF to trigger it (Development Mode)
        // If Session exists but hasn't started, we just wait for UXF to start it (via UI).
        if (session == null || !session.enabled)
        {
             // DANGER: This was causing pre-mature start during setup if Session wasn't found immediately.
             // Only auto-start if we are SURE we are in a debug scene without UXF Rig.
             // Better to just log a warning and WAIT.
             Debug.Log("[ExperimentManager] No UXF Session active/found. Waiting... (If debugging without UXF, manually call BeginTrial)");
             // StartCoroutine(SessionRoutine()); // <--- DISABLED AUTO-START to prevent premature running
        }
        else if (session.hasInitialised) 
        {
             // If session is ALREADY running (e.g. scene reload during experiment), resume?
             // Usually UXF handles this.
        }
        else
        {
            // Normal UXF Flow: We wait for user to click "Start" in UXF UI.
            // Do NOT auto-start SessionRoutine here, or it will conflict with UXF's BeginTrial.
            Debug.Log("[ExperimentManager] UXF Session detected. Waiting for 'Start' command from UXF UI.");
        }

        if (e2eMode && session != null && !session.hasInitialised)
        {
            if (string.IsNullOrWhiteSpace(e2eExperimentName)) e2eExperimentName = "highway_fatigue_settings";
            if (string.IsNullOrWhiteSpace(e2ePpid)) e2ePpid = $"e2e_{DateTime.UtcNow:yyyyMMdd_HHmmss}_{UnityEngine.Random.Range(1000, 9999)}";

            if (!string.IsNullOrWhiteSpace(e2eUxfRoot))
            {
                var handlers = FindObjectsOfType<LocalFileDataHander>(true);
                foreach (var h in handlers)
                {
                    h.dataSaveLocation = DataSaveLocation.Fixed;
                    h.StoragePath = e2eUxfRoot;
                }
            }

            Debug.Log($"[ExperimentManager] E2E Begin | Experiment={e2eExperimentName} PPID={e2ePpid} Session={e2eSessionNumber} Root={e2eUxfRoot} DistScale={e2eDistanceScale} PracticeSec={e2ePracticeDurationSeconds} BlockSec={e2eMainBlockDurationSeconds} StanfordSec={e2eStanfordTimeoutSeconds} EndDelaySec={e2eEndDelaySeconds}");
            session.Begin(e2eExperimentName, e2ePpid, e2eSessionNumber);
        }
    }

    /*
    // Called by UXF when session begins
    // DEPRECATED: ExperimentDirector.cs now handles Experiment Generation
    public void GenerateExperiment(Session session)
    {
        // Resume Game when Session Begins!
        Time.timeScale = 1f;
        AudioListener.pause = false;

        // ABBA Design Implementation
        // Participants (N=35) across 2 days (Sessions).
        // Group 1 (Odd PPID): Day 1 = GreenBelt (A), Day 2 = NoGreenBelt (B)
        // Group 2 (Even PPID): Day 1 = NoGreenBelt (B), Day 2 = GreenBelt (A)
        
        int ppidInt = 0;
        int.TryParse(session.ppid, out ppidInt);
        
        bool isGroup1 = (ppidInt % 2 != 0); // Odd
        bool isSession1 = (session.number == 1);
        
        string selectedCondition = "";
        
        if (isGroup1)
        {
            // A then B
            selectedCondition = isSession1 ? greenBeltCondition : noGreenBeltCondition;
        }
        else
        {
            // B then A
            selectedCondition = isSession1 ? noGreenBeltCondition : greenBeltCondition;
        }
        
        Debug.Log($"[Experiment] Generating Session {session.number} for PPID {session.ppid}. Selected Main Condition: {selectedCondition}");

        // --- BLOCK 1: PRACTICE / TEST (8 Mins) ---
        Block practiceBlock = session.CreateBlock(1);
        practiceBlock.settings.SetValue("type", "Practice");
        practiceBlock.settings.SetValue("condition", "Practice"); // Special condition name
        practiceBlock.settings.SetValue("duration_minutes", 8);

        // --- BLOCKS 2-4: MAIN EXPERIMENT (3 x 20 Mins) ---
        // These blocks use the selected condition (A or B)
        for (int i = 0; i < 3; i++)
        {
            Block block = session.CreateBlock(1); 
            block.settings.SetValue("type", "Main");
            block.settings.SetValue("condition", selectedCondition);
            block.settings.SetValue("duration_minutes", 20); 
        }
    }
    */

    // [New] Auto-start the first block when Session begins
    void OnSessionBegin(Session session)
    {
        Debug.Log("[ExperimentManager] Session Begun.");
        Debug.Log($"[ExperimentManager] Session Snapshot | SessionNum={session.number} PPID={session.ppid} Raw={(treadmillSystem != null ? treadmillSystem.totalVirtualDistance.ToString("F1") : "N/A")} BaselineRaw={(treadmillSystem != null ? distanceBaselineRaw.ToString("F1") : "N/A")} TotalDist={totalDistanceTraveled:F1} MainLoaded={mainScheduleLoaded} MainCount={mainTriggeredEventCount} MainNext={mainNextEventIndex}");

        // Force ExperimentDirector to generate the experiment (Blocks/Conditions)
        ExperimentDirector director = FindObjectOfType<ExperimentDirector>();
        if (director != null)
        {
            Debug.Log("[ExperimentManager] Found Director. Generating Experiment...");
            director.GenerateExperiment(session);
        }
        else
        {
            Debug.LogError("[ExperimentManager] ExperimentDirector NOT FOUND! Experiment sequence may be incorrect.");
        }

        Debug.Log("[ExperimentManager] Auto-starting Block 1.");
        StartNextBlock();
    }

    // [Added] Helper to Reset both cars to start
    public void ResetCarsToStart()
    {
        // Reset Player
        if (playerCar != null)
        {
            // 1. Reset Physics First
            Rigidbody rb = playerCar.GetComponent<Rigidbody>();
            if (rb != null)
            {
                rb.velocity = Vector3.zero;
                rb.angularVelocity = Vector3.zero;
                rb.Sleep(); // Important to stop physics momentum
            }

            // 2. Set Transform (Directly set position and rotation)
            playerCar.position = initialCarPosition;
            playerCar.rotation = initialCarRotation;
            
            // 3. Reset RCC Controller Inputs
            RCCP_CarController rcc = playerCar.GetComponent<RCCP_CarController>();
            if (rcc != null)
            {
                 rcc.throttleInput_P = 0f;
                 rcc.brakeInput_P = 0f;
                 rcc.steerInput_P = 0f;
                 rcc.handbrakeInput_P = 0f;
                 
                 // [Fix] Reset Gear to 0 or N
                 rcc.currentGear = 0;
            }
            
            // 4. Force update Transform again (Physics sync)
            playerCar.position = initialCarPosition;
            Physics.SyncTransforms(); 
        }

        // Reset Lead Car
        if (leadCar != null)
        {
            leadCar.ResetToStart();
        }
        
        Debug.Log($"[ExperimentManager] All Cars Reset to Start Position. Player: {initialCarPosition}");
    }

    public void BeginTrial(Trial trial)
    {
        // 0. Resume Game Time if it was paused
        if (Time.timeScale == 0f)
        {
            Time.timeScale = 1f;
            AudioListener.pause = false;
        }

        // 1. Get condition and phase
        string condition = trial.settings.GetString("condition", "");
        if (string.IsNullOrEmpty(condition))
            condition = trial.block != null ? trial.block.settings.GetString("condition", "") : "";
        currentConditionPrefix = condition + "_";
        
        int phaseIndex = trial.block.settings.GetInt("block_index", 0);
        string stage = trial.block.settings.GetString("stage", "");
        if (trial.numberInBlock == 1)
        {
            SendMarker($"{currentConditionPrefix}UXF_BlockStart", pulseInDrivingData: true);
        }
        
        // RESET LOGIC:
        // Reset distance only if it's the start of Practice or Start of Main Experiment (Phase 1)
        // For continuous blocks (Phase 2, 3), we DO NOT reset distance so the car continues seamlessly.
        bool isPracticeBlock = condition == "Practice" || stage == "Practice";
        bool shouldResetDistance = (isPracticeBlock || phaseIndex == 1);
        
        // [Added] Update Practice Flags
        isCurrentBlockPractice = isPracticeBlock;
        isPracticeEndSequenceStarted = false; // Reset the sequence flag
        if (isCurrentBlockPractice) 
        {
            practiceScaleTriggered = false;
        }

        if (shouldResetDistance)
        {
            if (treadmillSystem != null)
            {
                distanceBaselineRaw = treadmillSystem.totalVirtualDistance;
                totalDistanceTraveled = 0f;
            }
            else
            {
                totalDistanceTraveled = 0f;
            }
            zDistanceTraveled = 0f;
            speedDistanceTraveled = 0f;
            
            // [Fix] Reset Position to Start
            ResetCarsToStart();
            
            if (playerCar != null)
            {
                // Ensure lastFrameZ is synced to current position so we start counting from 0 delta
                lastFrameZ = playerCar.transform.position.z;
            }
            Debug.Log($"[ExperimentManager] Resetting Distance & Position for new Phase (Condition: {condition}, Phase: {phaseIndex}). Start Z: {lastFrameZ}");
        }
        else
        {
            // IMPORTANT FIX: For Phase 2/3 (Continuous Blocks), we must ensure totalDistanceTraveled is inherited.
            // However, CheckDistanceEvents checks against the absolute distance values in fixedSchedule.
            // If totalDistanceTraveled is reset or lost, events won't trigger.
            // Assuming totalDistanceTraveled is a member variable, it should persist across trials if we don't reset it.
            // The code above (if (shouldResetDistance)) correctly protects it.
            
            // Just update lastFrameZ to ensure continuity, but keep accumulated distance
            if (playerCar != null)
            {
                lastFrameZ = playerCar.transform.position.z;
            }
            Debug.Log($"[ExperimentManager] Continuing Distance for Phase {phaseIndex}. Current Total Distance: {totalDistanceTraveled}");
        }

        totalDrivingDuration = 0f; // ALWAYS Reset timer for the new block/trial duration check
        
        int secondsOverride = trial.block.settings.GetInt("duration_seconds", -1);
        if (e2eMode)
        {
            if (isPracticeBlock && e2ePracticeDurationSeconds > 0) secondsOverride = e2ePracticeDurationSeconds;
            if (!isPracticeBlock && e2eMainBlockDurationSeconds > 0) secondsOverride = e2eMainBlockDurationSeconds;
        }

        if (secondsOverride > 0)
        {
            currentTrialDurationLimit = secondsOverride;
        }
        else
        {
            int minutes = trial.block.settings.GetInt("duration_minutes", -1);
            currentTrialDurationLimit = minutes > 0 ? minutes * 60f : -1f;
        }

        if (isPracticeBlock && currentTrialDurationLimit <= 0)
        {
            currentTrialDurationLimit = 480f;
        }

        Debug.Log($"[ExperimentManager] Beginning Trial. Condition: {condition}, Phase: {phaseIndex}, Duration Limit: {currentTrialDurationLimit}s");

        // 2. Setup Environment
        // Only reload environment if we are resetting (start of new condition/practice)
        // For Phase 2/3, we assume environment is already set.
        if (shouldResetDistance)
        {
            // Re-find green belt if missing (in case scene changed or object was destroyed)
            if (greenBeltObject == null)
            {
                var obj = GameObject.Find("median"); // [Changed] User confirmed name is "median"
                if (obj == null) obj = GameObject.Find("GreenBeltParent");
                if (obj == null) obj = GameObject.Find("GreenBelt");
                if (obj == null) obj = GameObject.Find("Vegetation");
                if (obj != null) greenBeltObject = obj;
            }

            if (condition == "Practice")
            {
                // Load Practice Scene or Config
                Debug.Log("[ExperimentManager] Loading PRACTICE Environment...");
                // Practice has NO green belt to prevent bias
                if(greenBeltObject != null) greenBeltObject.SetActive(false); 
            }
            else if (condition == greenBeltCondition)
            {
                Debug.Log("[ExperimentManager] Loading GREEN BELT Environment...");
                if(greenBeltObject != null) greenBeltObject.SetActive(true);
            }
            else if (condition == noGreenBeltCondition)
            {
                Debug.Log("[ExperimentManager] Loading NO GREEN BELT Environment...");
                if(greenBeltObject != null) greenBeltObject.SetActive(false);
            }

            if (greenBeltObject != null)
                Debug.Log($"[ExperimentManager] GreenBelt SetActive: {greenBeltObject.activeSelf} for Condition: {condition}");
            else
                Debug.LogError("[ExperimentManager] GreenBelt Object is NULL! Cannot toggle visibility.");
        }

        // 3. Load Schedule
        if (isPracticeBlock)
        {
            PrepareEvents(condition, phaseIndex);
            practiceEventTimes.Clear();
            float dur = Mathf.Max(1f, currentTrialDurationLimit);
            float margin = dur / 24f;
            float interval = dur / 12f;
            for (int i = 0; i < 12; i++) practiceEventTimes.Add(margin + (interval * i));
            practiceNextEventIndex = 0;
        }
        else
        {
            bool isMainSegmentStart = phaseIndex == 1;
            EnsureMainScheduleLoaded(condition, resetProgress: isMainSegmentStart);
        }

        Debug.Log($"[ExperimentManager] Trial Snapshot | BlockNum={trial.block.number} BlockIndex={phaseIndex} TrialInBlock={trial.numberInBlock} Condition={condition} TotalDist={totalDistanceTraveled:F1} BaselineRaw={(treadmillSystem != null ? distanceBaselineRaw.ToString("F1") : "N/A")} MainNext={mainNextEventIndex} MainCount={mainTriggeredEventCount} MainLoaded={mainScheduleLoaded}");

        // 4. Start the Driving Session Logic
        StartCoroutine(SessionRoutine());
    }

    [Header("Manual Controls")]
    public bool triggerEventManually = false;
    public ExperimentEventType manualEventType;
    public bool testStanfordScale = false;
    
    [Header("Debug AI")]
    [Tooltip("If true, ignores NavMesh and forces Simple Cruise (straight line)")]
    public bool forceSimpleCruise = true; 
    
    [Tooltip("Check to enable RCCP AI on the player vehicle for auto-driving testing")]
    public bool debugEnablePlayerAI = false;

    void Update()
    {
        // Debug: Toggle AI
        if (debugEnablePlayerAI)
        {
            debugEnablePlayerAI = false;
            TogglePlayerAI(true);
        }
        
        // Debug: Force End Trial with 'E' key
        if (Input.GetKeyDown(KeyCode.E))
        {
            // Debug what Session thinks is happening
            Debug.Log($"[ExperimentManager] E pressed. Session status: InTrial={session.InTrial}, CurrentTrialNum={session.currentTrialNum}, CurrentBlockNum={session.currentBlockNum}");

            // Check InTrial first to avoid NoSuchTrialException
            // Relaxed check: if currentTrialNum > 0, we assume a trial is active or at least created
            if (session != null && session.currentTrialNum > 0)
            {
                Debug.Log("[ExperimentManager] Manual End Trial Triggered by Key 'E'");
                Trial endingTrial = session.CurrentTrial;
                isExperimentRunning = false;
                totalDrivingDuration = 0;
                if (endingTrial != null) endingTrial.End();
            }
            else
            {
                Debug.LogWarning("[ExperimentManager] Cannot end trial: No trial is currently running!");
            }
        }

        // Toggle AI with 'P' key
        if (Input.GetKeyDown(KeyCode.P))
        {
            // Find current state: either RCCP_AI is enabled OR Simple Cruise is active
            bool currentState = false;
            
            if (isSimpleCruiseActive)
            {
                currentState = true;
            }
            else if (playerCar != null)
            {
                var ai = playerCar.GetComponent<RCCP_AI>();
                if (ai != null && ai.enabled) currentState = true;
            }
            
            // Toggle
            Debug.Log($"[ExperimentManager] 'P' pressed. Current AI State: {currentState}. Toggling to {!currentState}.");
            TogglePlayerAI(!currentState);
        }

        // Simple Cruise Control Logic (Fallback for missing NavMesh)
        if (isSimpleCruiseActive && playerCar != null)
        {
            var car = playerCar.GetComponent<RCCP_CarController>();
            if (car != null)
            {
                // [Fix] Force Engine and Physics Awake
                if (!car.engineRunning) car.StartEngine();
                if (car.Rigid.IsSleeping()) car.Rigid.WakeUp();
                
                // [Fix] Force Direction (Drive)
                if (car.direction != 1) car.direction = 1;
                
                // [Fix] Force Gear (if Neutral/Reverse)
                var gearbox = car.GetComponentInChildren<RCCP_Gearbox>();
                if (gearbox != null)
                {
                    // Ensure transmission is Automatic
                    if (gearbox.transmissionType != RCCP_Gearbox.TransmissionType.Automatic)
                    {
                        gearbox.transmissionType = RCCP_Gearbox.TransmissionType.Automatic;
                    }

                    // Force Forward Gear if not moving forward
                    if (gearbox.currentGearState.gearState != RCCP_Gearbox.CurrentGearState.GearState.InForwardGear)
                    {
                        gearbox.ShiftToGear(0); // Shift to 1st gear
                        gearbox.currentGearState.gearState = RCCP_Gearbox.CurrentGearState.GearState.InForwardGear;
                    }
                    
                    // [Added] Force Shift Up if hitting rev limiter and not shifting
                    if (!gearbox.shiftingNow && car.engineRPM > (car.maxEngineRPM * 0.95f) && car.currentGear < gearbox.gearRatios.Length - 1)
                    {
                        gearbox.ShiftUp();
                        Debug.Log($"[ExperimentManager] SimpleCruise: Force Shift UP due to High RPM ({car.engineRPM:F0})");
                    }
                }

                float throttle = 0f;
                float brake = 0f;
                float currentSpeedKmh = car.speed;
                float targetSpeedKmh = avgSpeedEstimate * 3.6f; // Use configured speed (28 m/s * 3.6 = ~100 km/h)

                // Speed Control Logic (Improved P-Controller)
                float speedError = targetSpeedKmh - currentSpeedKmh;

                if (speedError > 5f)
                {
                    throttle = 1f; // Full throttle if significantly slower
                    brake = 0f;
                }
                else if (speedError < -2f)
                {
                    throttle = 0f; // Coast if slightly faster
                    brake = 0.1f; // Light brake
                }
                else
                {
                    // Proportional control for fine-tuning near target speed
                    // Base throttle to maintain speed + proportional error correction
                    // At 100km/h, drag requires ~0.3-0.5 throttle usually
                    throttle = 0.4f + (0.1f * speedError); 
                    throttle = Mathf.Clamp01(throttle);
                    brake = 0f;
                }
                
                // Override if car is stopped/stuck (kickstart)
                if (currentSpeedKmh < 10f && throttle < 0.5f) throttle = 1f;

                // Safety: Brake if too close to Lead Car (Emergency Only)
                if (leadCar != null)
                {
                     float dist = Vector3.Distance(playerCar.position, leadCar.transform.position);
                     // Only brake if VERY close to avoid crashing
                     if (dist < 20f) 
                     {
                         throttle = 0f;
                         brake = 1f; // Emergency brake
                         Debug.LogWarning($"[ExperimentManager] Emergency Brake! Distance to Lead: {dist:F1}m");
                     }
                }

                // Apply inputs via RCCP_Input to respect externalControl
                var inputComp = car.GetComponentInChildren<RCCP_Input>();
                if (inputComp != null)
                {
                    if (!inputComp.overridePlayerInputs) inputComp.overridePlayerInputs = true;
                    
                    if (inputComp.inputs == null) inputComp.inputs = new RCCP_Inputs();
                    
                    inputComp.inputs.throttleInput = throttle;
                    inputComp.inputs.brakeInput = brake;
                    inputComp.inputs.steerInput = 0f;
                    inputComp.inputs.handbrakeInput = 0f;
                }

                car.throttleInput_P = throttle;
                car.brakeInput_P = brake;
                car.steerInput_P = 0f; // Keep steering straight
                car.handbrakeInput_P = 0f;
                
                // Ensure external control is on
                if (!car.externalControl) car.externalControl = true;
                if (!car.canControl) car.canControl = true;
                
                // Debug log every second
                if (Time.frameCount % 60 == 0) {
                    Debug.Log($"[SimpleCruise] Spd: {currentSpeedKmh:F1} km/h | T: {throttle:F2} | B: {brake:F2} | Gear: {car.currentGear} | RPM: {car.engineRPM:F0} | Eng: {car.engineRunning}");
                }
            }
        }

        // Debug Trigger
        if (triggerEventManually)
        {
            triggerEventManually = false;
            StartCoroutine(RunEvent(manualEventType));
            Debug.Log($"[ExperimentManager] Manual Trigger: {manualEventType}");
        }

        if (testStanfordScale)
        {
            testStanfordScale = false;
            if (stanfordScale != null)
            {
                StartCoroutine(stanfordScale.ShowWithTimeout(8f, (val) => {
                    Debug.Log($"[StanfordScale] Test Result: {val}");
                }));
            }
        }

        // Enforce camera safety every frame
        // If main camera is missing (destroyed), try to find a new one or report critical error
        if (Camera.main == null && RCCP_SceneManager.Instance.activePlayerCamera == null)
        {
             // This is the "No cameras rendering" state
             // We can't easily recover if the object is destroyed, but we can prevent logic from crashing
        }
        else if (RCCP_SceneManager.Instance.activePlayerCamera != null && playerCar != null)
        {
             // Continuously ensure target is playerCar
             if (RCCP_SceneManager.Instance.activePlayerCamera.cameraTarget.playerVehicle != playerCar.GetComponent<RCCP_CarController>())
             {
                 RCCP_SceneManager.Instance.activePlayerCamera.SetTarget(playerCar.GetComponent<RCCP_CarController>());
             }
        }

        // Use isExperimentRunning flag set by BeginTrial -> SessionRoutine
        if (!isExperimentRunning || playerCar == null) return;

        float currentZ = playerCar.transform.position.z;
        float deltaZ = currentZ - lastFrameZ;
        if (deltaZ < -100f) deltaZ = 0f;
        if (deltaZ > 0f) zDistanceTraveled += deltaZ;
        lastFrameZ = currentZ;

        float speedKmh = 0f;
        var carCtrl = playerCar.GetComponent<RCCP_CarController>();
        if (carCtrl != null) speedKmh = carCtrl.speed;
        float speedMs = speedKmh / 3.6f;
        if (speedMs > 0.01f) speedDistanceTraveled += speedMs * Time.deltaTime;

        if (treadmillSystem != null)
        {
            float rawDist = Mathf.Max(0f, treadmillSystem.totalVirtualDistance - distanceBaselineRaw);
            totalDistanceTraveled = Mathf.Max(rawDist, speedDistanceTraveled, zDistanceTraveled);
        }
        else
        {
            totalDistanceTraveled = Mathf.Max(speedDistanceTraveled, zDistanceTraveled);
        }
        
        // Track Duration
        if (isExperimentRunning)
        {
            totalDrivingDuration += Time.deltaTime;
            
            // Debug Log every 30 seconds to confirm timer is running
            if (Time.frameCount % 1800 == 0) // Approx every 30s at 60fps
            {
                Debug.Log($"[ExperimentManager] Timer Running: {totalDrivingDuration:F1}s / {currentTrialDurationLimit:F1}s");
            }
            
            // [Added] Practice Mode Specific Logic: Show Stanford Scale at END (480s) not 450s
            // Previous 450s logic removed to avoid confusion.
            /*
            if (isCurrentBlockPractice && !practiceScaleTriggered && totalDrivingDuration >= 450f)
            {
                // Logic moved to block end
            }
            */

            // Auto-End Block Logic (Simplified and Robust)
            if (currentTrialDurationLimit > 0 && totalDrivingDuration >= currentTrialDurationLimit)
            {
                // --- Determine if Practice Mode ---
                bool isPractice = false;
                if (session != null && session.currentBlockNum > 0 && session.blocks != null && session.currentBlockNum <= session.blocks.Count)
                {
                    var currentBlock = session.blocks[session.currentBlockNum - 1];
                    string bType = currentBlock.settings.GetString("type", "");
                    string bCond = currentBlock.settings.GetString("condition", "");
                    
                    if (bType.Equals("Practice", System.StringComparison.OrdinalIgnoreCase) || 
                        bCond.Equals("Practice", System.StringComparison.OrdinalIgnoreCase) || 
                        currentBlock.number == 1)
                    {
                        isPractice = true;
                    }
                }

                if (isPractice)
                {
                    // [Key Change] Practice Mode: Do NOT End() directly! Intercept and show Scale THEN popup.
                    // Use flag to prevent multiple triggers
                    if (!isPracticeEndSequenceStarted)
                    {
                        isPracticeEndSequenceStarted = true;
                        Debug.Log("[ExperimentManager] Practice Block Time Limit Reached. Triggering Scale Sequence.");
                        
                        // DO NOT Pause game here - allow driving while scale is shown
                        // Time.timeScale = 1f; (Default)
                        
                        if (stanfordScale != null)
                        {
                            Debug.Log($"[ExperimentManager] Activating Stanford Scale Object. Current ActiveSelf: {stanfordScale.gameObject.activeSelf}");
                            
                            // [Fix] Force Scale Object Active
                            stanfordScale.gameObject.SetActive(true);
                            
                            // [Fix] Force Panel Active (in case UI script didn't)
                            if (stanfordScale.panel != null) stanfordScale.panel.SetActive(true);
                            
                            // Check hierarchy
                            if (!stanfordScale.gameObject.activeInHierarchy)
                            {
                                Debug.LogWarning($"[ExperimentManager] StanfordScale activeInHierarchy is FALSE. Checking parents...");
                                var parent = stanfordScale.transform.parent;
                                while (parent != null)
                                {
                                    if (!parent.gameObject.activeSelf)
                                    {
                                        Debug.LogWarning($"[ExperimentManager] Activating parent: {parent.name}");
                                        parent.gameObject.SetActive(true);
                                    }
                                    parent = parent.parent;
                                }
                            }

                            Debug.Log("[ExperimentManager] Starting ShowWithTimeout Coroutine...");
                            float stanfordSec = (e2eMode && e2eStanfordTimeoutSeconds > 0f) ? e2eStanfordTimeoutSeconds : 10f;
                            StartCoroutine(stanfordScale.ShowWithTimeout(stanfordSec, (val) => {
                                Debug.Log($"[StanfordScale] Practice Result: {val}. Showing Practice Popup.");
                                SendMarker($"StanfordScale_Practice_{val}");
                                
                                // After Scale finishes (10s), show the popup AND PAUSE
                                ShowPracticeLoopPopup();
                            }));
                        }
                        else
                        {
                            // Fallback if no scale
                            Debug.LogError("[ExperimentManager] Stanford Scale Reference is NULL! Skipping to Popup.");
                            ShowPracticeLoopPopup();
                        }
                    }
                }
                else
                {
                    Debug.Log($"[ExperimentManager] Block Duration Reached ({currentTrialDurationLimit}s). Ending Trial.");
                    TriggerMainBlockEnd();
                }
                
                // Note: For Practice, do NOT set duration to negative yet, 
                // because we need ShowPracticeLoopPopup to decide whether to reset it or keep it.
                if (!isPractice)
                {
                    totalDrivingDuration = -9999f; 
                }
            }
        }

        // 2. Loop Logic REMOVED (Handled by InfiniteLoopSystem)

        // 3. Event Trigger Logic (Distance Based)
        CheckDistanceEvents();
    }

    void TriggerMainBlockEnd()
    {
        // Official Experiment: Show Stanford Scale
        if (stanfordScale != null)
        {
            float stanfordSec = (e2eMode && e2eStanfordTimeoutSeconds > 0f) ? e2eStanfordTimeoutSeconds : 10f;
            float endDelaySec = (e2eMode && e2eEndDelaySeconds >= 0f) ? e2eEndDelaySeconds : 30f;
            StartCoroutine(stanfordScale.ShowWithTimeout(stanfordSec, (val) => {
                Debug.Log($"[StanfordScale] End-of-Block Result: {val}");
                SendMarker($"StanfordScale_BlockEnd_{val}");
                
                // DELAY: Wait 30 seconds after questionnaire before ending trial
                StartCoroutine(EndTrialWithDelay(endDelaySec));
            }));
        }
        else
        {
            // Fallback if no scale UI
            if (session.CurrentTrial != null)
            {
                isExperimentRunning = false;
                totalDrivingDuration = 0;
                session.CurrentTrial.End();
            }
        }
    }
    
    IEnumerator EndTrialWithDelay(float delay)
    {
        Debug.Log($"[ExperimentManager] Scale finished. Waiting {delay} seconds before ending trial...");
        Trial endingTrial = session != null ? session.CurrentTrial : null;
        yield return new WaitForSeconds(delay);
        
        if (session != null && endingTrial != null && session.CurrentTrial == endingTrial)
        {
            isExperimentRunning = false; 
            totalDrivingDuration = 0; 
            Debug.Log("[ExperimentManager] Trial Ended. Waiting for ExperimentController to handle Block transition.");
            endingTrial.End();
        }
    }

    /* OnGUI removed in favor of ExperimentController UI */

    // LoopBackToStart Removed - Handled by InfiniteLoopSystem
    /*
    void LoopBackToStart()
    {
        // ... (Original Logic) ...
    }
    */

    private string currentRunningEventName = "";

    public string GetCurrentRunningEventName()
    {
        return currentRunningEventName;
    }

    void CheckDistanceEvents()
    {
        if (isCurrentBlockPractice)
        {
            while (practiceNextEventIndex < practiceEventTimes.Count && totalDrivingDuration >= practiceEventTimes[practiceNextEventIndex])
            {
                ScheduledEvent nextEvent;
                if (fixedSchedule.Count > 0)
                {
                    nextEvent = fixedSchedule[0];
                    fixedSchedule.RemoveAt(0);
                }
                else
                {
                    int idx = practiceNextEventIndex + 1;
                    nextEvent = new ScheduledEvent { distance = 0f, type = ExperimentEventType.BrakingOnly, eventName = $"Practice_Braking_{idx}", remark = "" };
                }

                currentRunningEventName = GetEventBaseName(nextEvent.eventName);
                string markerName = BuildMarkerName(nextEvent.eventName);
                SendMarker(markerName, pulseInDrivingData: true);

                StartCoroutine(RunEvent(nextEvent.type));
                practiceNextEventIndex++;
                Debug.Log($"[Experiment] Triggered PRACTICE Event {markerName} at t={totalDrivingDuration:F1}s");
            }

            return;
        }

        if (!mainScheduleLoaded || mainSchedule.Count == 0) return;

        while (mainNextEventIndex < mainSchedule.Count && totalDistanceTraveled >= mainSchedule[mainNextEventIndex].distance)
        {
            ScheduledEvent nextEvent = mainSchedule[mainNextEventIndex];
            mainNextEventIndex++;
            mainTriggeredEventCount++;

            currentRunningEventName = GetEventBaseName(nextEvent.eventName);
            string markerName = BuildMarkerName(nextEvent.eventName);
            SendMarker(markerName, pulseInDrivingData: true);

            StartCoroutine(RunEvent(nextEvent.type));
            Debug.Log($"[Experiment] Triggered MAIN Event {markerName} #{mainTriggeredEventCount}/36 at {totalDistanceTraveled:F1}m (Target: {nextEvent.distance}m) | Block={session?.currentBlockNum} BlockIndex={session?.CurrentBlock?.settings.GetInt("block_index", -1)}");

            if (!string.IsNullOrEmpty(nextEvent.remark))
            {
                Debug.Log($"[Experiment] Special Remark Triggered: {nextEvent.remark}");
                SendMarker($"Remark_{nextEvent.remark}", pulseInDrivingData: false);

                if ((nextEvent.remark.Contains("Scale") || nextEvent.remark.Contains("Questionnaire")) && stanfordScale != null)
                {
                    float stanfordSec = (e2eMode && e2eStanfordTimeoutSeconds > 0f) ? e2eStanfordTimeoutSeconds : 10f;
                    StartCoroutine(stanfordScale.ShowWithTimeout(stanfordSec, (val) => {
                        Debug.Log($"[StanfordScale] User selected: {val}");
                        SendMarker($"StanfordScale_Result_{val}", pulseInDrivingData: false);
                    }));
                }
            }
        }
    }
    
    // --- Block Transition Logic ---
    void HandleBlockEnd(Block block)
    {
        Debug.Log($"[ExperimentManager] Block {block.number} Ended. Triggering Popup Logic.");
        Debug.Log($"[ExperimentManager] BlockEnd Snapshot | BlockNum={block.number} BlockIndex={block.settings.GetInt("block_index", -1)} Type={block.settings.GetString("type", "")} Condition={block.settings.GetString("condition", "")} Raw={(treadmillSystem != null ? treadmillSystem.totalVirtualDistance.ToString("F1") : "N/A")} BaselineRaw={(treadmillSystem != null ? distanceBaselineRaw.ToString("F1") : "N/A")} TotalDist={totalDistanceTraveled:F1} MainLoaded={mainScheduleLoaded} MainCount={mainTriggeredEventCount} MainNext={mainNextEventIndex}/36");
        string prefix = block.settings.GetString("condition", "");
        if (!string.IsNullOrEmpty(prefix)) prefix = prefix + "_";
        else prefix = currentConditionPrefix;
        SendMarker($"{prefix}UXF_BlockEnd", pulseInDrivingData: true);
        
        string blockType = block.settings.GetString("type", "");
        string blockCondition = block.settings.GetString("condition", "");

        if (blockType.Equals("Practice", System.StringComparison.OrdinalIgnoreCase) ||
            blockCondition.Equals("Practice", System.StringComparison.OrdinalIgnoreCase) ||
            block.number == 1)
        {
            // Pause game time immediately when practice block ends
            Time.timeScale = 0f;
            AudioListener.pause = true;

            // [Modified] Since we handle the "Practice Loop Popup" in Update(),
            // reaching here means the user has already clicked "OK" to finish practice.
            // So we just proceed directly to the next block without showing another popup.
            Debug.Log("[ExperimentManager] Practice Block Finished (User confirmed). Starting Next Block.");
            StartNextBlock();
        }
        else if (block.number < session.blocks.Count)
        {
            // Main Experiment Blocks (Block 2, 3...) - Auto Continue
            // Do NOT pause time for main blocks to ensure continuity
            Debug.Log($"[ExperimentManager] Continuous Mode: Auto-starting Block {block.number + 1}...");
            Time.timeScale = 1f; // Ensure time is resumed
            AudioListener.pause = false;
            StartNextBlock();
        }
        else
        {
            // All Blocks Finished
            // Pause game time immediately when all blocks end
            Time.timeScale = 0f;
            AudioListener.pause = true;

            Debug.Log("[ExperimentManager] Showing Experiment End Popup.");
            ShowBreakPopup("实验结束", "实验结束！\n\n感谢您的参与。", null);
            SendMarker($"{prefix}UXF_RunEnd", pulseInDrivingData: true);
            if (e2eMode && session != null && !e2eSessionEnded)
            {
                e2eSessionEnded = true;
                session.End();
            }
            if (e2eMode && e2eQuitOnFinish) Application.Quit();
        }
    }

    void ShowBreakPopup(string title, string message, System.Action onOK, System.Action onRestart = null)
    {
        // [Fix 1] Ensure finding PopupController (even if hidden)
        if (popupController == null)
        {
            // Use Resources.FindObjectsOfTypeAll to find hidden objects
            var allPopups = Resources.FindObjectsOfTypeAll<PopupController>();
            if (allPopups.Length > 0) popupController = allPopups[0];
        }

        // [Fix 2] Fix UI Occlusion (Issue 1)
        // Explicitly disable Startup Panel, regardless of its previous state
        if (startupPanel != null)
        {
            startupPanel.SetActive(false);
            Debug.Log("[ExperimentManager] Explicitly disabled Startup Panel.");
        }
        else
        {
            // Fallback: try finding by name if not assigned in Inspector
            GameObject sp = GameObject.Find("Startup Panel");
            if (sp != null) sp.SetActive(false);
        }

        if (popupController != null)
        {
            // Activate parent Canvas (This might try to show Startup Panel, but we forced it off above)
            Transform t = popupController.transform;
            while (t != null)
            {
                t.gameObject.SetActive(true);
                t = t.parent;
            }
            
            // Show Popup
            Popup popup = new Popup();
            popup.messageType = MessageType.Attention;
            popup.customTitle = title;
            popup.message = message;
            popup.onOK = onOK != null ? onOK : () => { };
            popup.onRestart = onRestart;
            popupController.DisplayPopup(popup);
        }
        else
        {
            // [Note] If PopupController is truly missing, skip to avoid getting stuck
            Debug.LogError("Critical Error: PopupController not found in scene! Auto-skipping popup to next stage.");
            if (onOK != null) onOK.Invoke();
        }
    }

    void ShowPracticeLoopPopup()
    {
        // 1. Pause Logic (optional: pause time or physics)
        Time.timeScale = 0f; // Ensure paused
        AudioListener.pause = true;

        // 2. Show Popup
        ShowBreakPopup(
            "练习结束",
            "练习时间已到。点击 'OK' 进入正式实验，或点击 'Restart' 重新练习。",
            
            // --- Logic for OK ---
            () => {
                Debug.Log("[ExperimentManager] User selected End Practice -> Proceed to Next Block.");
                
                // [Fix] Reset Cars BEFORE starting next block to ensure clean state for Block 2
                ResetCarsToStart();

                Time.timeScale = 1f; // Resume time
                AudioListener.pause = false;
                
                // ONLY HERE do we tell UXF: Block 1 is finished.
                if (session.CurrentTrial != null) session.CurrentTrial.End();
            },
            
            // --- Logic for Restart ---
            () => {
                Debug.Log("[ExperimentManager] User selected Retry Practice.");
                Time.timeScale = 1f; // Resume time
                AudioListener.pause = false;
                
                // [CORE]: Reset state to let Block 1 continue running
                totalDrivingDuration = 0f; // Reset timer
                totalDistanceTraveled = 0f; // Reset distance logic
                zDistanceTraveled = 0f;
                speedDistanceTraveled = 0f;
                practiceNextEventIndex = 0;
                
                // Reload Practice Events so they happen again
                PrepareEvents("Practice", 1);
                practiceEventTimes.Clear();
                for (int i = 0; i < 12; i++)
                {
                    practiceEventTimes.Add(20f + (40f * i));
                }
                
                // [Fix] Reset Vehicle Position
                ResetCarsToStart();
                if (playerCar != null) lastFrameZ = playerCar.transform.position.z;
                
                // Note: Do NOT call BeginNextTrial, and do NOT End().
                // As soon as the popup closes and timer resets, the user feels like it restarted.
            }
        );
    }

    public void StartNextBlock()
    {
        // session.currentBlockNum is 1-based index of CURRENT block.
        // session.blocks is 0-based list.
        // So session.blocks[session.currentBlockNum] gives the NEXT block (index = currentNum).
        
        if (session.currentBlockNum < session.blocks.Count)
        {
            Debug.Log($"[ExperimentManager] Starting Next Block (Index {session.currentBlockNum} -> Block {session.currentBlockNum + 1})...");
            
            Block nextBlock = session.blocks[session.currentBlockNum]; 
            
            if (nextBlock.trials.Count > 0)
            {
                nextBlock.trials[0].Begin();
            }
            else
            {
                Debug.LogError($"[ExperimentManager] Next block ({nextBlock.number}) has no trials!");
            }
        }
        else
        {
            Debug.Log("[ExperimentManager] No more blocks to run.");
        }
    }

    // Override SessionRoutine to just wait for start
    IEnumerator SessionRoutine()
    {
        isExperimentRunning = true;
        currentStatus = "RestPeriod";
        SendMarker($"{currentConditionPrefix}RestPeriod_Start");
        Debug.Log("[ExperimentManager] Starting Rest Period (90s)...");
        
        yield return new WaitForSeconds(initialRestTime);
        
        SendMarker($"{currentConditionPrefix}RestPeriod_End");
        Debug.Log("[ExperimentManager] Rest Ended. Starting Distance Monitoring.");

        // No random generation anymore. Fixed schedule is already loaded in PrepareEvents()
    }

    IEnumerator RunEvent(ExperimentEventType type)
    {
        ExperimentSkill skillToRun = null;
        switch (type)
        {
            case ExperimentEventType.OncomingOnly:
                skillToRun = oncomingSkill;
                break;
            case ExperimentEventType.BrakingOnly:
                // Sync parameters from Manager to Skill to ensure Inspector settings take effect
                if (brakingSkill is Skill_BrakingEvent bSkill) 
                {
                    bSkill.deceleration = brakingOnlyDecel;
                }
                skillToRun = brakingSkill;
                break;
            case ExperimentEventType.Combined:
                // Sync parameters from Manager to Skill
                if (combinedSkill is Skill_CombinedEvent cSkill) 
                {
                    cSkill.deceleration = combinedDecel;
                    cSkill.delayBeforeBrake = combinedEventDelay;
                }
                skillToRun = combinedSkill;
                break;
        }

        if (skillToRun != null)
        {
            Debug.Log($"[ExperimentManager] Executing Skill: {skillToRun.GetType().Name}");
            yield return StartCoroutine(skillToRun.Execute(this));
            
            // --- TRIAL SWITCHING LOGIC ---
            // Automatically advance to the next trial when an event (skill) finishes.
            // This aligns with the requirement: 1 Event = 1 Trial.
            if (!isSkippingBlock && session != null && session.InTrial && session.currentBlockNum > 0 && session.blocks != null && session.currentBlockNum <= session.blocks.Count)
            {
                 var currentBlock = session.blocks[session.currentBlockNum - 1];
                 if (currentBlock == null || currentBlock.trials == null || currentBlock.trials.Count <= 1) yield break;
                 
                 // Only advance if there is a NEXT trial available in this block
                 // CurrentTrial.numberInBlock is 1-based index of current trial.
                 // So if we are at Trial 1, next index in list is 1 (Trial 2).
                 int nextTrialIndex = session.CurrentTrial.numberInBlock; 
                 
                 if (nextTrialIndex < currentBlock.trials.Count)
                 {
                     Debug.Log($"[ExperimentManager] Event Finished. Ending Trial {session.CurrentTrial.numberInBlock} and Starting Trial {nextTrialIndex + 1}...");
                     session.CurrentTrial.End();
                     currentBlock.trials[nextTrialIndex].Begin();
                 }
                 else
                 {
                     Debug.Log($"[ExperimentManager] Last Event/Trial Finished (Trial {session.CurrentTrial.numberInBlock}). Keeping active until block time ends.");
                 }
            }
        }
        else
        {
            Debug.LogError($"[ExperimentManager] No skill assigned for event type: {type}");
        }
    }

    public void SpawnBus()
    {
        if (busPrefab == null || playerCar == null) return;

        // Straight road simplified logic (since we use EndlessRoadHandler)
        // We can just spawn ahead on Z axis instead of using spline indices if the road is straight.
        
        // However, BusAI uses spline indices. Let's keep using spline for consistency if possible.
        // But wait, if we are near the end of the road (before teleport), the bus spawn might fail
        // because there are no indices ahead.
        // In "Endless" mode, if we are near end, we might need to spawn bus AFTER teleport?
        // Or just spawn it physically and let BusAI snap to nearest spline point.
        
        if (roadUtils != null)
        {
            // Try spline method first
            int playerIndex = roadUtils.GetClosestPointIndex(playerCar.position);
            
            // Validate playerIndex to prevent ArgumentOutOfRangeException
            if (playerIndex < 0 || playerIndex >= roadUtils.GetPointCount())
            {
                Debug.LogWarning($"[ExperimentManager] SpawnBus failed: Invalid playerIndex {playerIndex} (Total Points: {roadUtils.GetPointCount()})");
                return;
            }

            int spawnIndex = playerIndex;
            float distAccum = 0;
            bool found = false;
            
            for (int i = playerIndex; i < roadUtils.GetPointCount(); i++)
            {
                // Safety check to ensure i+1 is valid
                if (i + 1 >= roadUtils.GetPointCount()) break;
                distAccum += Vector3.Distance(roadUtils.GetPointAtIndex(i), roadUtils.GetPointAtIndex(i+1));
                if (distAccum >= oncomingSpawnDistance)
                {
                    spawnIndex = i;
                    found = true;
                    break;
                }
            }
            
            // If not found (end of road), we should spawn "virtually" ahead (which means near start of road?)
            // This is complex. 
            // Alternative: If not found, just don't spawn bus this time? Or spawn closer?
            // Given 2km road and 250m spawn dist, it should be fine most of the time unless we are at 1.8km.
            // If at 1.8km, teleport will happen soon.
            // Let's just spawn it if found.
            
            if (found)
            {
                GameObject busObj = Instantiate(busPrefab);
                BusAI busAI = busObj.GetComponent<BusAI>();
                if (busAI == null) busAI = busObj.AddComponent<BusAI>();
                busAI.Initialize(spawnIndex, busSpeed, -3.75f);
            }
            else
            {
                Debug.LogWarning("[ExperimentManager] Could not spawn bus: End of road reached.");
            }
        }
    }

    public void SendMarker(string marker, bool pulseInDrivingData = false)
    {
        int blockNum = -1;
        int blockIndex = -1;
        int trialInBlock = -1;
        if (session != null && session.InTrial)
        {
            blockNum = session.currentBlockNum;
            if (session.currentBlockNum > 0 && session.blocks != null && session.currentBlockNum <= session.blocks.Count)
                blockIndex = session.blocks[session.currentBlockNum - 1].settings.GetInt("block_index", -1);
            if (session.CurrentTrial != null) trialInBlock = session.CurrentTrial.numberInBlock;
        }

        try
        {
            if (lslStream != null)
            {
                lslStream.SendMarker(marker);
            }
        }
        catch (System.DllNotFoundException)
        {
            Debug.LogWarning($"[LSL] DLL Not Found! Marker '{marker}' was NOT sent to LSL stream.");
        }
        catch (System.Exception e)
        {
            Debug.LogWarning($"[LSL] Error sending marker: {e.Message}");
        }
        
        Debug.Log($"[LSL Marker] {marker}");

        if (pulseInDrivingData)
        {
            string enriched = marker;
            if (blockNum > 0 && trialInBlock > 0)
            {
                double lc = LSL.LSL.local_clock();
                string lcStr = lc.ToString("F6", CultureInfo.InvariantCulture);
                string utStr = Time.time.ToString("F6", CultureInfo.InvariantCulture);
                string rtStr = Time.realtimeSinceStartup.ToString("F6", CultureInfo.InvariantCulture);
                enriched = $"{marker}|B{blockNum}|BI{blockIndex}|TB{trialInBlock}|LC{lcStr}|UT{utStr}|RT{rtStr}";
                try
                {
                    if (lslStream != null) lslStream.SendMarker(enriched);
                }
                catch { }
                Debug.Log($"[LSL Marker] {enriched}");
            }

            currentStatus = enriched;
            Debug.Log($"[EventDebug] marker=1 | BlockNum={blockNum} BlockIndex={blockIndex} TrialInBlock={trialInBlock} TotalDist={totalDistanceTraveled:F1} MainCount={mainTriggeredEventCount} MainNext={mainNextEventIndex}/36");
        }
    }

    // Called by Logger after it reads the status to clear it (Pulse Mode)
    public void ClearCurrentEventStatus()
    {
        currentStatus = "";
    }

    public string GetCurrentEventStatus()
    {
        return currentStatus;
    }

    // --- Helper for Debug AI ---
    [ContextMenu("Enable Player AI")]
    public void EnablePlayerAI() => TogglePlayerAI(true);
    
    [ContextMenu("Disable Player AI")]
    public void DisablePlayerAI() => TogglePlayerAI(false);

    [ContextMenu("Debug: Skip Current Block")]
    public void DebugSkipBlock()
    {
        Debug.Log("[ExperimentManager] Debug Command: Skipping Current Block...");
        
        // Check if it's practice mode
        bool isPractice = false;
        
        // [Fix] Check if session is actually running a block (currentBlockNum > 0)
        // session.CurrentBlock throws ArgumentOutOfRangeException if blocks is empty or currentBlockNum is invalid
        if (session != null && session.currentBlockNum > 0 && session.currentBlockNum <= session.blocks.Count)
        {
            // Use safe GetString
            string bType = session.CurrentBlock.settings.GetString("type", "");
            string bCond = session.CurrentBlock.settings.GetString("condition", "");
            
            if (bType.Equals("Practice", System.StringComparison.OrdinalIgnoreCase) || 
                bCond.Equals("Practice", System.StringComparison.OrdinalIgnoreCase) || 
                session.CurrentBlock.number == 1)
            {
                isPractice = true;
            }
        }
        else
        {
             Debug.LogWarning("[ExperimentManager] Cannot determine practice mode (No active block). Assuming Standard Mode.");
        }

        if (isPractice)
        {
             // For Practice, "Skip" means "Time is Up" -> Show Popup
             Debug.Log("[ExperimentManager] Debug Skip (Practice Mode) -> Showing Practice Loop Popup");
             ShowPracticeLoopPopup();
        }
        else
        {
            if (session == null)
            {
                Debug.LogWarning("[ExperimentManager] No session. Cannot skip block.");
                return;
            }

            if (session.currentBlockNum >= session.blocks.Count)
            {
                Debug.LogWarning("[ExperimentManager] Already at last block. Cannot skip forward.");
                return;
            }

            isSkippingBlock = true;

            try
            {
                if (session.currentBlockNum > 0 && session.currentBlockNum <= session.blocks.Count)
                {
                    string cond = session.CurrentBlock.settings.GetString("condition", "");
                    int blockIndex = session.CurrentBlock.settings.GetInt("block_index", -1);
                    int boundary = Mathf.Clamp(blockIndex * 12, 0, 36);
                    if (boundary > 0)
                    {
                        mainNextEventIndex = Mathf.Max(mainNextEventIndex, boundary);
                        mainTriggeredEventCount = Mathf.Max(mainTriggeredEventCount, boundary);
                    }

                    float targetDist = 0f;
                    if (cond == greenBeltCondition)
                    {
                        if (blockIndex == 1) targetDist = 33000f;
                        else if (blockIndex == 2) targetDist = 66000f;
                        else if (blockIndex == 3) targetDist = 99000f;
                    }
                    else if (cond == noGreenBeltCondition)
                    {
                        if (blockIndex == 1) targetDist = 32200f;
                        else if (blockIndex == 2) targetDist = 65800f;
                        else if (blockIndex == 3) targetDist = 99400f;
                    }

                    if (targetDist > 0f)
                    {
                        if (treadmillSystem != null)
                        {
                            distanceBaselineRaw = treadmillSystem.totalVirtualDistance - targetDist;
                        }
                        totalDistanceTraveled = targetDist;
                    }
                }

                fixedSchedule.Clear();
                totalDrivingDuration = 0f;
                isExperimentRunning = false;

                if (session.InTrial && session.CurrentTrial != null)
                {
                    session.CurrentTrial.End();
                }

                StartNextBlock();
            }
            finally
            {
                isSkippingBlock = false;
            }
        }
    }

#if UNITY_EDITOR
    void OnGUI()
    {
        // Simple Debug Button for testing flow
        if (GUI.Button(new Rect(10, 50, 150, 40), "Skip Block (Debug)"))
        {
            DebugSkipBlock();
        }
        
        if (isExperimentRunning)
        {
            GUI.Label(new Rect(10, 10, 300, 20), $"Block: {session.currentBlockNum} | Time: {totalDrivingDuration:F1}/{currentTrialDurationLimit:F1}");
        }
    }
#endif

    private bool isSimpleCruiseActive = false;

    void TogglePlayerAI(bool enable)
    {
        if (playerCar == null) return;
        
        var car = playerCar.GetComponent<RCCP_CarController>();
        if (car == null) return;
        
        // 1. Force Engine On
        if (enable && !car.engineRunning)
        {
            car.StartEngine();
        }
        
        // 2. Force Gear D
        if (enable) car.direction = 1; 
        
        // Check NavMesh availability
        bool hasNavMesh = false;
        
        // [Fix] Check forceSimpleCruise first to avoid unnecessary NavMesh checks
        if (!forceSimpleCruise)
        {
            UnityEngine.AI.NavMeshHit hit;
            if (UnityEngine.AI.NavMesh.SamplePosition(playerCar.position, out hit, 5.0f, UnityEngine.AI.NavMesh.AllAreas))
            {
                hasNavMesh = true;
            }
        }
        else
        {
            Debug.Log("[ExperimentManager] Force Simple Cruise is ON. Skipping NavMesh check.");
        }

        var ai = car.GetComponent<RCCP_AI>();
        
        if (enable)
        {
            // Enable External Control
            car.externalControl = true;
            car.canControl = true;

            if (hasNavMesh)
            {
                // Use RCCP AI
                if (ai == null) ai = car.gameObject.AddComponent<RCCP_AI>();
                
                if (ai.waypointsContainer == null)
                    ai.waypointsContainer = FindObjectOfType<RCCP_AIWaypointsContainer>();
                
                ai.enabled = true;
                isSimpleCruiseActive = false;
                Debug.Log($"[ExperimentManager] Player AI ENABLED (NavMesh Auto-Pilot). Engine: {car.engineRunning}");
            }
            else
            {
                // Fallback to Simple Cruise
                if (ai != null) ai.enabled = false; // Disable RCCP AI to prevent errors
                isSimpleCruiseActive = true;
                Debug.LogWarning("[ExperimentManager] Player AI ENABLED (Simple Cruise Mode). No NavMesh detected or Forced Simple Cruise! Car will drive straight.");
            }
        }
        else
        {
            // Disable AI
            isSimpleCruiseActive = false;
            
            if (ai != null) ai.enabled = false;
            
            // Restore control to player
            car.externalControl = false;
            car.canControl = true;
            
            // Reset Inputs to prevent "stuck" controls
            car.throttleInput_P = 0f;
            car.brakeInput_P = 0f;
            car.steerInput_P = 0f;
            car.handbrakeInput_P = 0f;
            
            Debug.Log("[ExperimentManager] Player AI DISABLED (Manual Mode). Inputs Reset.");
        }
    }
}
