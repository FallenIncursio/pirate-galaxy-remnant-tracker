import java.lang.reflect.*;
import java.util.*;

/** Allowlisted Remnant data only; no graphics dependencies. */
public final class RemnantData {
    static Object call(Object o,String n)throws Exception{return o.getClass().getMethod(n).invoke(o);}
    static Object field(Object o,String n)throws Exception {Class<?> c=o.getClass();while(c!=null){try{Field f=c.getDeclaredField(n);f.setAccessible(true);return f.get(o);}catch(NoSuchFieldException e){c=c.getSuperclass();}}throw new NoSuchFieldException(n);}
    static String quote(String s){
        StringBuilder out=new StringBuilder("\"");
        for(int i=0;i<s.length();i++){char c=s.charAt(i);
            if(c=='\\'||c=='"')out.append('\\').append(c);
            else if(c<32)out.append(String.format("\\u%04x",(int)c));
            else out.append(c);
        }return out.append('"').toString();
    }
    static String json(Object o){
        if(o==null)return "null";if(o instanceof Boolean||o instanceof Number)return o.toString();
        if(o instanceof Map){StringJoiner j=new StringJoiner(",","{","}");for(Object k:((Map<?,?>)o).keySet())j.add(quote(k.toString())+":"+json(((Map<?,?>)o).get(k)));return j.toString();}
        if(o instanceof Iterable){StringJoiner j=new StringJoiner(",","[","]");for(Object v:(Iterable<?>)o)j.add(json(v));return j.toString();}
        return quote(o.toString());
    }
    static Object raw(Object map,String key)throws Exception{return map.getClass().getMethod("getRawValue",String.class).invoke(map,key);}
    static List<Object> values(Object map)throws Exception{return (List<Object>)map.getClass().getMethod("getValues",Class.class).invoke(map,Object.class);}
    static List<Object> snapshot(Object c)throws Exception{
        List<Object> rows=new ArrayList<>();
        for(Object intel:values(field(c,"properties"))){
            if(!intel.getClass().getName().equals("com.splitscreen.aiq"))continue;
            Map<String,Object> row=new LinkedHashMap<>();row.put("intel_id",call(intel,"getUUID"));Object p=field(intel,"properties");
            for(String k:new String[]{"carrierName","spawnTime","carrierType","starSystem","blueprintCategory","planet","HPStatus"}){Object v=raw(p,k);row.put(k,v instanceof String||v instanceof Number||v instanceof Boolean?v:null);}
            Object timer=raw(p,"despawnTimer");if(timer!=null){row.put("timer_type",timer.getClass().getName());row.put("timer_remaining",call(timer,"sr"));row.put("timer_hidden",call(timer,"sv"));}
            rows.add(row);
        }return rows;
    }
}
